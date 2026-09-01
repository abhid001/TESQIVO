# Installing TESQIVO with Docker

TESQIVO is distributed as a single container image. You run it with Docker Compose
alongside PostgreSQL and Redis. There is no source checkout and no build step.

- **Time to a working instance:** ~2 minutes.
- **Image:** `ghcr.io/abhid001/tesqivo` (public, GitHub Container Registry).

---

## 1. Prerequisites

| Requirement | Notes |
|---|---|
| **Docker Engine 24+** with the Compose plugin | `docker compose version` must work. Docker Desktop (macOS/Windows) includes it. |
| ~1–2 GB RAM, ~2 GB disk | More as your test data grows. |
| One free TCP port | Default `8080`. |
| Outbound HTTPS from the host | To pull images from `ghcr.io` and `docker.io`. |

You do **not** need Python, Node, or a clone of the source.

---

## 2. Get the compose file and start

```bash
mkdir tesqivo && cd tesqivo
curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/docker-compose.yml
docker compose up -d
```

`docker compose` pulls the `tesqivo`, `postgres:16-alpine`, and `redis:7-alpine`
images and starts four containers: `web`, `worker`, `db`, `redis`. The `web`
container applies its database schema automatically on first start.

Check it came up:

```bash
docker compose ps
curl -s http://localhost:8080/api/v1/healthz     # {"status":"ok"}
curl -s http://localhost:8080/api/v1/version     # the running build
```

If `web` shows as restarting for the first 10–20 seconds, that is normal — it is
waiting for the database. It settles on its own.

---

## 3. Create the first administrator

```bash
docker compose exec web python -m app.cli create-admin
```

Answer the prompts:

- **Username** — e.g. `admin`
- **Email**
- **Display name**
- **Password** — at least 12 characters, with upper case, lower case, and a digit

Non-interactive (for scripted installs):

```bash
docker compose exec web python -m app.cli create-admin \
  --username admin --email admin@example.com --password 'Ch4nge-this-passphrase'
```

This command works only while no user exists. After this, add and manage people
from **Admin console → Users** inside the app.

---

## 4. Open it

Go to **http://localhost:8080** and sign in with the account you just created.

- API reference: `http://localhost:8080/api/v1/docs`
- OpenAPI spec: `http://localhost:8080/api/v1/openapi.json`

---

## 5. Configuration

**Nothing is required for a local trial.** For a deployment you intend to keep,
create a file named `.env` next to `docker-compose.yml`:

```dotenv
# Change the bundled database password from the default.
POSTGRES_PASSWORD=a-strong-database-password

# The EXACT URL people use to reach TESQIVO. Must be https:// for secure
# session cookies once you put it behind TLS.
TESQIVO_PUBLIC_URL=http://localhost:8080

# Host port to publish (default 8080). Use 127.0.0.1:8080 to bind to localhost
# only, e.g. when a separate reverse proxy terminates TLS.
TESQIVO_HTTP_PORT=8080

# Optional: pin a specific version instead of the latest release.
#TESQIVO_VERSION=v0.2.0
```

Then `docker compose up -d` again to apply.

| Variable | Default | Purpose |
|---|---|---|
| `POSTGRES_PASSWORD` | `tesqivo` | Bundled database password. |
| `TESQIVO_PUBLIC_URL` | `http://localhost:8080` | Absolute base URL for links and cookies. |
| `TESQIVO_HTTP_PORT` | `8080` | Host port. |
| `TESQIVO_VERSION` | `latest` | Image tag to run. |
| `TESQIVO_SECRET_KEY` | auto-generated | Session/CSRF secret (≥32 bytes). Generated on first boot and kept in the data volume so logins survive restarts. Set it yourself only to manage it manually or share it across hosts. |
| `TESQIVO_SMTP_HOST` / `_PORT` / `_USER` / `_PASSWORD` / `_FROM` | unset | Outbound email for self-service password reset. With email off, "Forgot password?" tells users to contact an administrator and admins reset accounts from the console. |

---

## 6. HTTPS

**Option A — built-in (Caddy, automatic Let's Encrypt).** Point a DNS record at
the host, then download the TLS overlay and start with both files:

```bash
curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/docker-compose.tls.yml
curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/deploy/Caddyfile --create-dirs -o deploy/Caddyfile

export TESQIVO_DOMAIN=tcms.example.com
export TESQIVO_PUBLIC_URL=https://tcms.example.com
docker compose -f docker-compose.yml -f docker-compose.tls.yml up -d
```

**Option B — your own proxy.** Keep the base file, set `TESQIVO_PUBLIC_URL` to your
public `https://` URL, set `TESQIVO_HTTP_PORT=127.0.0.1:8080`, and point
nginx / Traefik / a cloud load balancer at that local port. It must forward the
original `Host` header and route both `/` and `/api` to the same upstream.

---

## 7. Upgrading

```bash
docker compose pull
docker compose up -d
```

The `web` container reapplies any new database migrations on start. Confirm the
version afterwards:

```bash
curl -s http://localhost:8080/api/v1/version
```

Pin `TESQIVO_VERSION` in `.env` (e.g. `v0.2.0`) if you prefer explicit, reviewed
upgrades over tracking `latest`. **Back up before upgrading.**

---

## 8. Backup and restore

State lives in two Docker volumes: `tesqivo_pgdata` (database) and
`tesqivo_appdata` (`/data` — the generated secret key and uploaded attachments).

**Backup:**

```bash
docker compose exec -T db pg_dump -Fc -U tesqivo tesqivo > db-$(date +%F).dump
docker run --rm -v tesqivo_appdata:/data -v "$PWD":/backup alpine \
  tar czf /backup/appdata-$(date +%F).tgz -C /data .
```

**Restore into a running stack:**

```bash
cat db-2026-01-01.dump | docker compose exec -T db pg_restore --clean --if-exists -U tesqivo -d tesqivo
docker run --rm -v tesqivo_appdata:/data -v "$PWD":/host alpine \
  sh -c 'find /data -mindepth 1 -delete && tar xzf /host/appdata-2026-01-01.tgz -C /data'
docker compose restart web
```

Schedule the backup commands with cron and copy the files off the host. Test a
restore into a throwaway environment before you rely on it.

---

## 9. Day-to-day operations

```bash
docker compose logs -f web          # follow logs (add: worker, db)
docker compose exec web sh          # shell inside the app container
docker compose restart web          # restart a service
docker compose down                 # stop, keep all data
docker compose down -v              # stop AND delete all data
```

Health endpoints: `/api/v1/healthz` (liveness), `/api/v1/readyz` (database check),
`/api/v1/version` (build).

---

## 10. Troubleshooting

| Symptom | What to check |
|---|---|
| `web` keeps restarting | `docker compose logs web` — usually `db` not ready yet (it retries), or an invalid `TESQIVO_DB_URL` if you customised it. |
| Manifest / image pull error | Confirm the host can reach `ghcr.io`. The image is public; no login is needed. |
| Login works, then drops on refresh | `TESQIVO_PUBLIC_URL` must exactly match how you reach the app. An `https` URL is required for the value to say `https://`. |
| Blank page / assets 404 behind a proxy | The proxy must pass the original `Host` and route `/` and `/api` to the same upstream. |
| `create-admin` says an admin already exists | A user is already present — add people from **Admin console → Users** instead. |
| Port 8080 already in use | Set `TESQIVO_HTTP_PORT` to a free port in `.env`, then `docker compose up -d`. |

---

## 11. Uninstall

```bash
docker compose down -v          # removes containers AND the data volumes
docker rmi ghcr.io/abhid001/tesqivo
```

---

## Appendix — For maintainers: how the image is published

End users never build anything; the image is produced by CI.

1. Update `CHANGELOG.md` and bump `version` in `backend/pyproject.toml` and
   `__version__` in `backend/app/__init__.py`.
2. Merge to `main`, then tag and push:
   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```
3. `.github/workflows/release.yml` builds a multi-architecture image
   (`linux/amd64` + `linux/arm64`) and pushes
   `ghcr.io/abhid001/tesqivo:{v0.2.0, 0.2, latest}`. Pushes to `main` (without a
   tag) publish `:edge` only.
4. **First release only:** make the package public —
   *GitHub → your profile → Packages → `tesqivo` → Package settings → Change
   visibility → Public*. After that, `docker compose up -d` works for anyone.

Contributors who need to run a local build use
`docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build`
(`make up`); see `CONTRIBUTING.md`.
