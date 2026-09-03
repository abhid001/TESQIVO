# Self-hosting TESQIVO

TESQIVO runs as a single container image (`ghcr.io/abhid001/tesqivo`) alongside PostgreSQL
and Redis. You download one Compose file and start it — no source checkout, no build step,
and no configuration is required to try it.

## Prerequisites

- A host with **Docker Engine 24+** and the Compose plugin (`docker compose version`).
- ~1 GB RAM and 2 GB disk for a small team; more as your data grows.
- Outbound HTTPS so the host can pull images from `ghcr.io` and `docker.io`.

## Quick start

```bash
curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/docker-compose.yml
docker compose up -d
docker compose exec web python -m app.cli create-admin
```

Then open <http://localhost:8080> and sign in with the administrator you just created.

`create-admin` prompts for username, email, display name and password. For an unattended
install pass them as flags:

```bash
docker compose exec web python -m app.cli create-admin \
  --username admin --email admin@example.com --password 'Ch4nge-this-passphrase'
```

Passwords need at least 12 characters, an upper-case letter, a lower-case letter, a
digit, and a special character. It only works while
no user exists — afterwards, add people from the in-app admin console.

## Configuration

Nothing is required for a trial. For anything you intend to keep, create a `.env` file next
to `docker-compose.yml` (see [`.env.example`](../.env.example)) and set at least:

| Variable | Why |
|---|---|
| `POSTGRES_PASSWORD` | the bundled database password — change it from the default `tesqivo` |
| `TESQIVO_PUBLIC_URL` | the exact URL browsers use (e.g. `https://tcms.example.com`); it must be `https://` for secure session cookies |
| `TESQIVO_HTTP_PORT` | host port to publish (default `8080`; use `127.0.0.1:8080` to bind locally only) |

Other useful ones:

| Variable | Default | Notes |
|---|---|---|
| `TESQIVO_VERSION` | `latest` | pin a released tag, e.g. `v0.2.0` |
| `TESQIVO_SECRET_KEY` | auto-generated | a random key is created on first boot and stored at `/data/secret_key` inside the `appdata` volume so sessions survive restarts. Set this explicitly only if you want to manage it yourself or run more than one host against the same database. |
| `TESQIVO_SMTP_*` | unset | outbound email for self-service password reset. When set, "Forgot password?" emails a one-time link (valid 1 hour; the current password keeps working until it is used). With email off it tells users to contact an admin, who resets accounts from the console. Administrator accounts are never emailed and must be reset by a human. |

The app refuses to start only if `TESQIVO_DB_URL`, `TESQIVO_REDIS_URL` or
`TESQIVO_PUBLIC_URL` is genuinely invalid — the bundled Compose file provides all three.

## HTTPS

**Option A — built-in Caddy.** Point DNS for your hostname at the host, then:

```bash
export TESQIVO_DOMAIN=tcms.example.com
export TESQIVO_PUBLIC_URL=https://tcms.example.com
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

Caddy obtains and renews a Let's Encrypt certificate automatically.

**Option B — your own proxy.** Keep the base file, set `TESQIVO_PUBLIC_URL` to your public
`https://` URL, and point nginx / Traefik / a cloud load balancer at the published port.
Set `TESQIVO_HTTP_PORT=127.0.0.1:8080` so the plain-HTTP port is not exposed publicly.

## Upgrading

```bash
docker compose pull
docker compose up -d
```

The `web` container reapplies database migrations on start (they are idempotent). Check the
running build:

```bash
curl -s http://localhost:8080/api/v1/version
# {"version":"v0.2.0","environment":"production"}
```

Pin `TESQIVO_VERSION` in `.env` if you prefer explicit, reviewed upgrades over `:latest`.
Back up before upgrading.

## Backup and restore

State lives in two volumes: `tesqivo_pgdata` (database) and `tesqivo_appdata` (`/data` —
the generated secret key and uploaded attachments).

**Backup:**

```bash
docker compose exec -T db pg_dump -Fc -U tesqivo tesqivo > db-$(date +%F).dump
docker run --rm -v tesqivo_appdata:/data -v "$PWD":/backup alpine \
  tar czf /backup/appdata-$(date +%F).tgz -C /data .
```

**Restore** into a running stack:

```bash
cat db-2026-01-01.dump | docker compose exec -T db pg_restore --clean --if-exists -U tesqivo -d tesqivo
docker run --rm -v tesqivo_appdata:/data -v "$PWD":/host alpine \
  sh -c 'find /data -mindepth 1 -delete && tar xzf /host/appdata-2026-01-01.tgz -C /data'
docker compose restart web
```

From a repo checkout, `make backup` and `make restore BACKUP=… ATTACH=…` wrap these.

## Operations

- **Logs:** `docker compose logs -f web` (add `worker`, `db` as needed).
- **Health:** `GET /api/v1/healthz` (liveness), `GET /api/v1/readyz` (checks the database),
  `GET /api/v1/version` (build).
- **Shell:** `docker compose exec web sh`.
- **Reset a password** when SMTP is off: admin console → Users → the user → reset.
- **Stop / remove:** `docker compose down` (keeps volumes); add `-v` to delete data.

## Troubleshooting

| Symptom | Check |
|---|---|
| `web` restarts on boot | `docker compose logs web` — usually `db` not ready yet (it retries) or an invalid `TESQIVO_DB_URL` |
| Login works then drops on refresh | `TESQIVO_PUBLIC_URL` scheme/host must match how you actually reach the app; https requires the URL to say `https://` |
| `create-admin` says an admin already exists | a user is already present — use the admin console instead |
| Assets 404 / blank page behind a proxy | proxy must forward the original `Host` and pass `/` and `/api` to the same upstream |
| Image pull denied | the package is public; check the host has outbound access to `ghcr.io` |

## Building from source

Contributors don't use the published image — see [`CONTRIBUTING.md`](../CONTRIBUTING.md).
`make up` builds the image locally via `docker-compose.dev.yml`.
