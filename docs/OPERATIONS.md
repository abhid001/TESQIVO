# TESQIVO Operations Guide

## Supported environment (decision D-013)

| Component | Supported |
|---|---|
| Docker Engine | 24+ |
| PostgreSQL | 16 |
| Redis | 7 |
| Browsers | latest 2 stable Chrome, Edge, Firefox |

## Configuration

All configuration is via `TESQIVO_*` environment variables. Nothing is required
for a local trial — the bundled `docker-compose.yml` supplies working defaults.
The process refuses to start with a single clear log line if `TESQIVO_DB_URL`,
`TESQIVO_REDIS_URL` or `TESQIVO_PUBLIC_URL` is invalid (no stack trace, no secret
echo). `TESQIVO_SECRET_KEY` is auto-generated and persisted at `/data/secret_key`
when unset. Full contract and env table: `docs/self-hosting.md`.

## First run

```bash
curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/docker-compose.yml
docker compose up -d
docker compose exec web python -m app.cli create-admin
```

The `web` container applies `alembic upgrade head` on start (idempotent); the
worker skips it (`TESQIVO_AUTO_MIGRATE=0`). `create-admin` works only while no
user exists; the browser "create first administrator" screen (gated by
`TESQIVO_BOOTSTRAP_TOKEN`) is the alternative.

## Health

- `GET /api/v1/healthz` — liveness (process up).
- `GET /api/v1/readyz` — readiness (database reachable); returns 503 when degraded.
- `GET /api/v1/version` — the running build.
- Compose healthchecks gate `web` and `worker` on `db` + `redis`.

## Upgrades

```bash
docker compose pull
docker compose up -d       # the web entrypoint re-applies migrations
```

Pin `TESQIVO_VERSION` (e.g. `v0.2.0`) in `.env` for reviewed upgrades instead of
`:latest`. Confirm with `GET /api/v1/version`.

Migration compatibility policy: a release never removes a column still read by the
previous minor version. Destructive migrations are split across two releases
(add + backfill, then remove).

## Backup & restore

```bash
make backup
# -> backups/db-YYYYMMDD-HHMMSS.dump  (pg_dump -Fc)
# -> backups/appdata-YYYYMMDD-HHMMSS.tgz  (the /data volume: secret + attachments)

make restore BACKUP=backups/db-XXXX.dump ATTACH=backups/appdata-XXXX.tgz
```

Restore drops and recreates schema objects (`pg_restore --clean --if-exists`),
replaces the `appdata` volume contents, then restarts `web` (its entrypoint
re-applies migrations). Raw commands without a checkout: `docs/self-hosting.md`.
**Test restore into a clean environment before relying on it** (acceptance §19.10).

Initial internal targets: RPO 24h, RTO 4h. Schedule `make backup` via cron and
copy `./backups/` off-host.

## Data retention (open — OQ-4)

`user_session`, resolved `background_job`, and import staging files accumulate.
Until a retention policy is set, prune manually:

```sql
DELETE FROM user_session WHERE expires_at < now() - interval '30 days';
```

## Rate limiting (OQ-3)

Phase 1 uses an in-process sliding-window limiter (per client IP + path class);
auth endpoints are capped tighter. Stale keys are swept so memory stays bounded.
Behind a proxy or Cloudflare, set `TESQIVO_TRUSTED_PROXIES` (IPs / CIDRs, or `*`)
so the limiter keys on the real client IP from `CF-Connecting-IP` /
`X-Forwarded-For` rather than the proxy address. For multi-instance deployments,
front with a shared limiter (reverse proxy or a Redis token bucket) — documented
as the upgrade path, not implemented in Phase 1.

## Observability

Structured logs to stdout with `correlation_id`. Every request/response carries
`X-Correlation-ID`. Audit events (`audit_event` table) are append-only and
queryable by authorized users.
