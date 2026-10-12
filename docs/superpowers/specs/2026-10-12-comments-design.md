# Comments Design (Artalk on the VPS)

Date: 2026-10-12
Status: approved design, pending spec review

## Goal

Readers of the book site (GitHub Pages, mostly non-GitHub users) can leave
public comments and report corrections under every page — including the
landing page and front texts like «Предисловие», but not the print view.
Comments are anonymous (nickname only, no account). The author moderates
from an admin panel.

## Decisions already made

- System: **Artalk** (MIT, single Go binary + SQLite, Russian UI, anonymous
  comments, admin panel, captcha available later). Chosen over hosted
  services (Disqus/VK — third-party tracking/ads), GitHub-account widgets
  (giscus/utterances — audience cannot log in to GitHub), and Render.com
  free tier (spins down, no persistent disk, expires).
- Hosting: user's existing Hetzner VPS (4 GB RAM, runs other services),
  **no Docker** — systemd + existing nginx.
- Hostname: `comments.spkenny.ru` (A record added 2026-10-12, Cloudflare
  DNS, **DNS-only/grey cloud**, resolves to 204.168.247.247). TLS via
  `certbot --nginx` (normal 90-day Let's Encrypt certs).
- Placement: every built page except `print.html`.

## Architecture

### Server side (deploy guide the user runs; no repo automation)

- **Artalk v2.10.0** binary from GitHub release
  `artalk_v2.10.0_linux_amd64.tar.gz` (checksums.txt published), installed
  as `/usr/local/bin/artalk`.
- **systemd unit** `artalk.service`: runs `artalk -w /var/lib/artalk server`,
  restarts on failure, starts after network.
- **Config** `/var/lib/artalk/artalk.yml`:
  - `host: 127.0.0.1`, `port: 23366` (never exposed directly)
  - `app_key`: random string (generated during deploy)
  - `locale: ru`, `timezone: Europe/Moscow`
  - `db: { type: sqlite, file: ./data/artalk.db }`
  - `site_default: Интернат`
  - `trusted_domains: [https://ssppkenny.github.io]` (CORS: the book site
    origin)
  - `http.proxy_header: X-Forwarded-For` (real reader IPs behind nginx)
  - `log: { enabled: true, filename: ./data/artalk.log }`
- **Admin account**: created once with the `artalk admin` CLI command
  (exact flags verified during deployment). Dashboard at
  `https://comments.spkenny.ru`.
- **nginx**: one new server block `comments.spkenny.ru` reverse-proxying to
  `http://127.0.0.1:23366`, forwarding Host and `X-Forwarded-For`; then
  `certbot --nginx -d comments.spkenny.ru`. Existing vhosts untouched.
- The Artalk server serves the client assets itself at `/dist/Artalk.js`
  and `/dist/Artalk.css`.

### Site side (implemented in this repo)

- New file `site/theme/custom.js`, wired via
  `[output.html] additional-js = ["theme/custom.js"]` in `site/book.toml`.
- On load, unless `location.pathname` ends with `print.html`:
  1. Append `<h2>Комментарии</h2>` + `<div id="artalk-comments">` to
     `<main>`.
  2. Inject `Artalk.css` and `Artalk.js` from
     `https://comments.spkenny.ru/dist/`.
  3. `Artalk.init({ el: '#artalk-comments', server: 'https://comments.spkenny.ru',
     site: 'Интернат', pageKey: location.pathname, pageTitle: document.title,
     locale: 'ru' })`.
  4. Dark mode follows the mdBook theme: dark for `coal`/`navy`/`ayu`
     classes on `<html>`; a MutationObserver on the class attribute keeps it
     in sync when the reader toggles the theme.
- Small CSS addition in `site/theme/custom.css` for the comments container
  (top margin/width so it blends with the text column).
- Defaults: comments publish immediately; admin edits/deletes in the panel.
  Captcha, email and Telegram notifications stay off; they are
  panel-configurable later without code changes.
- Graceful behavior: if the server is unreachable, Artalk shows its own
  loading/error state; the rest of the page is unaffected. The site change
  is pushed only after the server is verified live.

### Rollout order

1. User runs the deploy guide on the VPS; verifies `https://comments.spkenny.ru`
   answers (API health + dashboard login).
2. Repo change (custom.js + book.toml + css + deploy guide doc) is pushed
   after user confirmation.
3. Live verification: chapter page references the Artalk assets; a test
   comment posted from the live site appears; print.html has no widget.

Rollback: remove the `additional-js` line (widget disappears everywhere);
the VPS service is independent and can keep running or be stopped.

## Verification

- `python3 -m pytest tests/ -v` stays green (no converter changes).
- Local: `mdbook build site`; confirm `theme/custom-*.js` is linked on
  `index.html` and a chapter page; `node --check site/theme/custom.js`
  (or equivalent syntax check) passes.
- Server (user, via guide): `curl http://127.0.0.1:23366/api/v2/...` health
  check, `systemctl status artalk`, dashboard login, then
  `curl -I https://comments.spkenny.ru` → 200 with valid certificate.
- Live (after push): fetch a chapter page → Artalk script tag present;
  landing page and «Предисловие» page get the widget; print.html does not;
  post a real comment and see it appear.

## Risks

- `trusted_domains` must exactly match the site origin
  (`https://ssppkenny.github.io`); if the site ever moves, update it.
- Ports 80/443 must be open on the VPS for certbot (they already serve
  other sites, so this is expected).
- Anonymous comments attract spam eventually; mitigation is the admin
  panel, then captcha (built in, no code change).
- The exact `artalk admin` CLI syntax and nginx/systemd snippets are pinned
  in the implementation plan from the official v2.10.0 docs and verified
  during deployment.

## Files touched

- Create: `site/theme/custom.js`, `docs/comments-deploy.md`
  (step-by-step VPS guide for the user)
- Modify: `site/book.toml` (one line), `site/theme/custom.css` (small
  addition)
- Untouched: `internat/`, `Photos/`, `.github/workflows/pages.yml`

## Amendment 2026-10-12: auth and login timeout in the config

Verified on the deployed VPS: email/password login requires
`auth.enabled: true` and `auth.email.enabled: true`; the dashboard login
additionally requires `login_timeout: 259200` — with the default `0` Artalk
issues already-expired tokens (`exp == iat`), every authenticated API call
returns 403 «Need login», and the SPA loops back to the login form.
`docs/comments-deploy.md` and `docs/comments-install.sh` now write both keys.
`auth.anonymous: true` was added too: without it the widget requires
registration; with it readers post with just a nickname (verified locally on
v2.10.0 — the providers endpoint reports `anonymous: true`).
