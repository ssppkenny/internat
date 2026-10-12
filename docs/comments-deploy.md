# Deploying the Artalk comment server (comments.spkenny.ru)

Run these steps over SSH on the VPS (204.168.247.247) as a user with sudo.
Prerequisites: nginx already installed and running; ports 80/443 open; the
Cloudflare A record `comments.spkenny.ru` already exists and is **DNS-only**
(grey cloud) — keep it that way.

## 1. Install the Artalk binary (v2.10.0)

```bash
cd /tmp
curl -fsSLO https://github.com/ArtalkJS/Artalk/releases/download/v2.10.0/artalk_v2.10.0_linux_amd64.tar.gz
curl -fsSLO https://github.com/ArtalkJS/Artalk/releases/download/v2.10.0/checksums.txt
grep linux_amd64 checksums.txt
sha256sum artalk_v2.10.0_linux_amd64.tar.gz
tar -xzf artalk_v2.10.0_linux_amd64.tar.gz
sudo install -m 0755 artalk_v2.10.0_linux_amd64/artalk /usr/local/bin/artalk
artalk --version
```

The sha256 must be
`8ef3dcb322207ea76038a32d8e137604eba9313259c3423683d80efbcf18aed1`;
`artalk --version` must print `Artalk (v2.10.0)`.

## 2. Service user and directories

```bash
sudo useradd --system --home /var/lib/artalk --shell /usr/sbin/nologin artalk
sudo mkdir -p /var/lib/artalk/data
sudo chown -R artalk:artalk /var/lib/artalk
```

## 3. Configuration /var/lib/artalk/artalk.yml

```bash
KEY=$(openssl rand -hex 16)
sudo tee /var/lib/artalk/artalk.yml >/dev/null <<EOF
host: 127.0.0.1
port: 23366
app_key: $KEY
locale: ru
timezone: Europe/Moscow
auth:
  enabled: true
  email:
    enabled: true
login_timeout: 259200
db:
  type: sqlite
  file: ./data/artalk.db
site_default: Интернат
trusted_domains:
  - https://ssppkenny.github.io
http:
  proxy_header: X-Forwarded-For
log:
  enabled: true
  filename: ./data/artalk.log
EOF
sudo chown artalk:artalk /var/lib/artalk/artalk.yml
```

`auth.enabled` + `auth.email.enabled` are required for email/password login.
`login_timeout: 259200` (3 days) is required too — with the default `0` the
dashboard issues already-expired tokens and the login page loops forever.

## 4. systemd service

```bash
sudo tee /etc/systemd/system/artalk.service >/dev/null <<'EOF'
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
sudo systemctl daemon-reload
sudo systemctl enable --now artalk
systemctl status artalk --no-pager
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:23366/
```

Expect `302` from curl. The startup log shows an `ERROR ... [Email] Email
Sender initialize failed` line — that is expected and harmless (email
notifications are not configured).

## 5. Create the admin account

```bash
sudo -u artalk /usr/local/bin/artalk admin -w /var/lib/artalk \
  --name admin --email YOUR_EMAIL --password 'YOUR_PASSWORD'
```

The password lands in your shell history — run `history -d <n>` afterwards if
that matters to you. (Interactive mode needs a real terminal; do not pipe it.)

## 6. nginx + TLS

```bash
sudo tee /etc/nginx/sites-available/comments.spkenny.ru >/dev/null <<'EOF'
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
sudo ln -s /etc/nginx/sites-available/comments.spkenny.ru /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
sudo certbot --nginx -d comments.spkenny.ru
```

If your nginx keeps vhosts in `conf.d/` instead of `sites-available/`, put
the same server block there and reload.

## 7. Verify

```bash
curl -I https://comments.spkenny.ru
```

Expect `HTTP/2 302` (or 200) with a valid certificate. Open
`https://comments.spkenny.ru` in a browser and log in with the admin account;
the dashboard appears. Captcha, notifications, and social login can be enabled
later from the dashboard — no server changes needed.

## Upgrading Artalk later

Download the newer release tarball, verify its checksum, `sudo install` it
over `/usr/local/bin/artalk`, then `sudo systemctl restart artalk`.

## Rollback

`sudo systemctl disable --now artalk` stops comments; the site widget will
show a loading error until the repo-side `additional-js` line is removed.
