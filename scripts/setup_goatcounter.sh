#!/usr/bin/env bash
# Установка GoatCounter на Ubuntu 24.04 с уже работающим nginx.
#
# Запуск на сервере:
#   sudo bash setup_goatcounter.sh
#
# Можно переопределить параметры:
#   sudo DOMAIN=stats.example.com EMAIL=me@example.com bash setup_goatcounter.sh

set -euo pipefail

DOMAIN="${DOMAIN:-stats.spkenny.ru}"
EMAIL="${EMAIL:-}"
VERSION="${GOATCOUNTER_VERSION:-v2.7.0}"
PORT="${GOATCOUNTER_PORT:-8091}"
INSTALL_DIR="/opt/goatcounter"
SERVICE="/etc/systemd/system/goatcounter.service"
NGINX_SITE="/etc/nginx/conf.d/goatcounter.conf"
DB="$INSTALL_DIR/goatcounter-data/db.sqlite3"

log() { printf '\n==> %s\n' "$*"; }
die() { printf 'Ошибка: %s\n' "$*" >&2; exit 1; }

[[ $EUID -eq 0 ]] || die "запустите через sudo: sudo bash $0"

if [[ -z "$EMAIL" ]]; then
  read -r -p "Email для входа в GoatCounter: " EMAIL
fi
[[ -n "$EMAIL" ]] || die "email не указан"

case "$(uname -m)" in
  x86_64) ARCH=amd64 ;;
  aarch64) ARCH=arm64 ;;
  *) die "неизвестная архитектура: $(uname -m)" ;;
esac

log "Проверяю DNS для $DOMAIN"
for _ in $(seq 1 30); do
  if getent hosts "$DOMAIN" >/dev/null 2>&1; then
    break
  fi
  sleep 2
done
getent hosts "$DOMAIN" >/dev/null 2>&1 || \
  die "DNS для $DOMAIN ещё не резолвится; подождите и запустите снова"

log "Проверяю порт $PORT"
if ss -ltn | awk '{print $4}' | grep -qE "[:.]${PORT}$"; then
  die "порт $PORT уже занят; задайте GOATCOUNTER_PORT=другой"
fi

log "Устанавливаю certbot, если его нет"
if ! command -v certbot >/dev/null 2>&1; then
  apt-get update
  apt-get install -y certbot python3-certbot-nginx
fi

log "Создаю пользователя goatcounter"
if ! id goatcounter >/dev/null 2>&1; then
  adduser --system --group --home "$INSTALL_DIR" \
    --shell /usr/sbin/nologin goatcounter
fi
install -d -o goatcounter -g goatcounter "$INSTALL_DIR"

log "Скачиваю GoatCounter $VERSION"
if [[ ! -x "$INSTALL_DIR/goatcounter" ]]; then
  tmp="$(mktemp -d)"
  trap 'rm -rf "$tmp"' EXIT

  asset_url="$(
    curl -fsSL "https://api.github.com/repos/arp242/goatcounter/releases/tags/${VERSION}" |
    python3 -c '
import json, sys
data = json.load(sys.stdin)
name = f"goatcounter-{sys.argv[1]}-linux-{sys.argv[2]}.gz"
print(next(a["url"] for a in data["assets"] if a["name"] == name))
' "$VERSION" "$ARCH"
  )" || asset_url=""

  if [[ -n "$asset_url" ]] && \
    curl -fL --retry 8 --retry-delay 5 --retry-all-errors \
      -H "Accept: application/octet-stream" \
      -o "$tmp/goatcounter.gz" "$asset_url"; then
    gunzip -f "$tmp/goatcounter.gz"
  else
    log "Не удалось скачать бинарник; собираю GoatCounter из исходников"
    apt-get update
    apt-get install -y golang-go build-essential
    (cd "$tmp" && GOBIN="$tmp" \
      GOPROXY="https://proxy.golang.org,direct" \
      GOTOOLCHAIN=auto \
      CGO_ENABLED=1 \
      go install "zgo.at/goatcounter/v2/cmd/goatcounter@${VERSION}")
  fi

  install -o goatcounter -g goatcounter -m 0755 \
    "$tmp/goatcounter" "$INSTALL_DIR/goatcounter"
  rm -rf "$tmp"
  trap - EXIT
fi
"$INSTALL_DIR/goatcounter" version

log "Создаю сайт $DOMAIN"
if [[ ! -f "$DB" ]]; then
  (cd "$INSTALL_DIR" && runuser -u goatcounter -- ./goatcounter db create site \
    -createdb -vhost="$DOMAIN" -user.email="$EMAIL")
else
  echo "База уже существует: $DB"
  echo "Если сайта ещё нет, создайте его вручную:"
  echo "  cd $INSTALL_DIR && runuser -u goatcounter -- ./goatcounter db create site -createdb -vhost=$DOMAIN -user.email=$EMAIL"
fi

log "Настраиваю systemd"
cat > "$SERVICE" <<EOF
[Unit]
Description=GoatCounter analytics
After=network.target

[Service]
Type=simple
User=goatcounter
Group=goatcounter
WorkingDirectory=$INSTALL_DIR
ExecStart=$INSTALL_DIR/goatcounter serve -listen 127.0.0.1:$PORT -tls http
Restart=always
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable goatcounter
systemctl restart goatcounter

log "Жду, пока GoatCounter поднимется"
for _ in $(seq 1 30); do
  if curl -fsS -o /dev/null "http://127.0.0.1:$PORT/"; then
    break
  fi
  sleep 1
done
curl -fsS -o /dev/null "http://127.0.0.1:$PORT/" || \
  die "GoatCounter не отвечает на 127.0.0.1:$PORT; смотрите journalctl -u goatcounter"

log "Настраиваю nginx"
if [[ -f "$NGINX_SITE" ]]; then
  cp -a "$NGINX_SITE" "$NGINX_SITE.bak.$(date +%Y%m%d-%H%M%S)"
fi

cat > "$NGINX_SITE" <<EOF
server {
    listen 80;
    listen [::]:80;
    server_name $DOMAIN;

    location / {
        proxy_pass http://127.0.0.1:$PORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_http_version 1.1;
    }
}
EOF

nginx -t
systemctl reload nginx

log "Получаю HTTPS-сертификат"
certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect -m "$EMAIL"

log "Проверяю"
curl -fsS -o /dev/null "https://$DOMAIN/" && echo "Сайт доступен: https://$DOMAIN/"
curl -fsS -o /dev/null "https://$DOMAIN/count?p=%2Ftest&t=test" && \
  echo "Счётчик отвечает: https://$DOMAIN/count"

cat <<EOF

Готово.

Панель:      https://$DOMAIN/
Счётчик:     https://$DOMAIN/count
База:        $DB
Сервис:      systemctl status goatcounter
Логи:        journalctl -u goatcounter -f

Не забудьте сменить endpoint в site/theme/head.hbs на:
  https://$DOMAIN/count
EOF
