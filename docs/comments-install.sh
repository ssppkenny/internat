#!/usr/bin/env bash
# One-shot installer for the Artalk comment server (comments.spkenny.ru).
# Usage: sudo bash comments-install.sh
# Safe to re-run: existing config, database and admin account are kept.
set -euo pipefail

DOMAIN="comments.spkenny.ru"
PORT="23366"
ARTALK_VERSION="v2.10.0"
ARTALK_SHA256="8ef3dcb322207ea76038a32d8e137604eba9313259c3423683d80efbcf18aed1"
ARTALK_USER="artalk"
ARTALK_HOME="/var/lib/artalk"
BINARY="/usr/local/bin/artalk"
SITE_URL="https://ssppkenny.github.io"
SITE_NAME="Интернат"

if [[ $EUID -ne 0 ]]; then
  echo "error: run as root (sudo bash $0)" >&2
  exit 1
fi

step() { echo; echo "=== $* ==="; }

step "Artalk binary ($ARTALK_VERSION)"
if [[ -x "$BINARY" ]] && "$BINARY" --version >/dev/null 2>&1; then
  echo "already installed: $("$BINARY" --version) (keeping; delete $BINARY to force reinstall)"
else
  cd /tmp
  curl -fsSLO "https://github.com/ArtalkJS/Artalk/releases/download/${ARTALK_VERSION}/artalk_${ARTALK_VERSION}_linux_amd64.tar.gz"
  echo "${ARTALK_SHA256}  artalk_${ARTALK_VERSION}_linux_amd64.tar.gz" | sha256sum -c -
  tar -xzf "artalk_${ARTALK_VERSION}_linux_amd64.tar.gz"
  install -m 0755 "artalk_${ARTALK_VERSION}_linux_amd64/artalk" "$BINARY"
  "$BINARY" --version
fi

step "Service user and directories"
if ! id -u "$ARTALK_USER" >/dev/null 2>&1; then
  useradd --system --home "$ARTALK_HOME" --shell /usr/sbin/nologin "$ARTALK_USER"
fi
mkdir -p "$ARTALK_HOME/data"
chown -R "$ARTALK_USER:$ARTALK_USER" "$ARTALK_HOME"

step "Configuration $ARTALK_HOME/artalk.yml"
if [[ -f "$ARTALK_HOME/artalk.yml" ]]; then
  echo "exists — keeping it (app_key preserved)"
else
  command -v openssl >/dev/null || { apt-get update -qq && apt-get install -y -qq openssl; }
  KEY="$(openssl rand -hex 16)"
  cat > "$ARTALK_HOME/artalk.yml" <<EOF
host: 127.0.0.1
port: $PORT
app_key: $KEY
locale: ru
timezone: Europe/Moscow
auth:
  enabled: true
  anonymous: true
  email:
    enabled: true
login_timeout: 259200
db:
  type: sqlite
  file: ./data/artalk.db
site_default: $SITE_NAME
trusted_domains:
  - $SITE_URL
http:
  proxy_header: X-Forwarded-For
log:
  enabled: true
  filename: ./data/artalk.log
EOF
  chown "$ARTALK_USER:$ARTALK_USER" "$ARTALK_HOME/artalk.yml"
fi

step "systemd service"
cat > /etc/systemd/system/artalk.service <<'EOF'
[Unit]
Description=Artalk comment server
After=network.target

[Service]
User=artalk
WorkingDirectory=/var/lib/artalk
ExecStart=/usr/local/bin/artalk server
Restart=on-failure
RestartSec=3

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now artalk
systemctl restart artalk
code=""
for _ in $(seq 1 15); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$PORT/" || true)"
  [[ "$code" == "302" || "$code" == "200" ]] && break
  sleep 1
done
echo "local HTTP status: ${code:-none}"

step "Admin account"
read -r -p "Admin email (empty = skip): " ADMIN_EMAIL || true
CERT_EMAIL=""
if [[ -n "${ADMIN_EMAIL:-}" ]]; then
  read -r -p "Admin name [admin]: " ADMIN_NAME || true
  ADMIN_NAME="${ADMIN_NAME:-admin}"
  read -r -s -p "Admin password: " ADMIN_PASSWORD || true
  echo
  sudo -u "$ARTALK_USER" "$BINARY" admin -w "$ARTALK_HOME" \
    --name "$ADMIN_NAME" --email "$ADMIN_EMAIL" --password "${ADMIN_PASSWORD:-}" \
    || echo "note: admin may already exist (see error above)"
  unset ADMIN_PASSWORD
  CERT_EMAIL="$ADMIN_EMAIL"
fi

step "nginx vhost"
command -v nginx >/dev/null || { apt-get update -qq && apt-get install -y -qq nginx; }
if grep -qs 'sites-enabled' /etc/nginx/nginx.conf; then
  VHOST_DIR=/etc/nginx/sites-available
  VHOST_FILE="$VHOST_DIR/$DOMAIN"
  ENABLE_LINK=/etc/nginx/sites-enabled/$DOMAIN
else
  VHOST_DIR=/etc/nginx/conf.d
  VHOST_FILE="$VHOST_DIR/$DOMAIN.conf"
  ENABLE_LINK=""
fi
if [[ "$VHOST_DIR" == /etc/nginx/conf.d && ! -f "$VHOST_FILE" && -f "$VHOST_DIR/$DOMAIN" ]]; then
  mv "$VHOST_DIR/$DOMAIN" "$VHOST_FILE"
  echo "renamed $VHOST_DIR/$DOMAIN to $VHOST_FILE (conf.d requires the .conf suffix)"
fi
if [[ ! -f "$VHOST_FILE" ]]; then
  if [[ "$VHOST_DIR" != /etc/nginx/sites-available && -f "/etc/nginx/sites-available/$DOMAIN" ]]; then
    mv "/etc/nginx/sites-available/$DOMAIN" "$VHOST_FILE"
    rm -f "/etc/nginx/sites-enabled/$DOMAIN"
    echo "moved vhost from sites-available to $VHOST_FILE (sites-enabled is not included by nginx.conf)"
  elif [[ "$VHOST_DIR" != /etc/nginx/conf.d && -f "/etc/nginx/conf.d/$DOMAIN.conf" ]]; then
    mv "/etc/nginx/conf.d/$DOMAIN.conf" "$VHOST_FILE"
    echo "moved vhost from conf.d to $VHOST_FILE"
  fi
fi
if [[ -f "$VHOST_FILE" ]]; then
  echo "vhost exists — keeping it (TLS edits preserved)"
else
  cat > "$VHOST_FILE" <<'EOF'
server {
    listen 80;
    server_name comments.spkenny.ru;

    location / {
        proxy_pass http://127.0.0.1:23366;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
EOF
fi
if [[ -n "$ENABLE_LINK" ]]; then
  ln -sfn "$VHOST_FILE" "$ENABLE_LINK"
fi
nginx -t
systemctl reload nginx
if ! nginx -T 2>/dev/null | grep -q "configuration file .*$DOMAIN"; then
  echo "error: nginx did not load $VHOST_FILE — check that /etc/nginx/nginx.conf includes it" >&2
  exit 1
fi

step "TLS certificate"
if [[ ! -d "/etc/letsencrypt/live/$DOMAIN" ]] || ! grep -q 'ssl_certificate' "$VHOST_FILE"; then
  if ! command -v certbot >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq certbot python3-certbot-nginx
  elif ! dpkg -s python3-certbot-nginx >/dev/null 2>&1; then
    apt-get update -qq
    apt-get install -y -qq python3-certbot-nginx
  fi
  if [[ -z "$CERT_EMAIL" ]]; then
    read -r -p "Email for Let's Encrypt notices: " CERT_EMAIL || true
  fi
  if [[ -z "${CERT_EMAIL:-}" ]]; then
    echo "error: an email is required for Let's Encrypt — re-run and provide one" >&2
    exit 1
  fi
  certbot --nginx -d "$DOMAIN" --non-interactive --agree-tos --redirect -m "$CERT_EMAIL"
else
  echo "certificate and TLS vhost already present — keeping"
fi

step "Verify"
curl -sS -o /dev/null -w '%{url_effective} -> %{http_code}\n' "https://$DOMAIN/" || true
echo
echo "Done. Open https://$DOMAIN and log in with the admin account."
echo "Captcha, notifications and social login can be enabled later in the dashboard."
