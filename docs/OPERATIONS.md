# TESQIVO Operations Guide

## Supported environment (decision D-013)

| Component | Supported |
|---|---|
| Docker Engine | 24+ |
| PostgreSQL | 16 |
| Redis | 7 |
| Browsers | latest 2 stable Chrome, Edge, Firefox |

## Configuration

All configuration is via `TESQIVO_*` environment variables. The API refuses to
start with a single clear log line if a required variable is missing or invalid
(no stack trace, no secret echo). Full contract:
`docs/architecture/09_deployment.md`.

Required: `TESQIVO_DB_URL`, `TESQIVO_REDIS_URL`, `TESQIVO_SECRET_KEY` (≥32 bytes),
`TESQIVO_PUBLIC_URL`. Required on first boot: `TESQIVO_BOOTSTRAP_TOKEN`.

## First run

```bash
cp .env.example .env
# TESQIVO_SECRET_KEY=$(openssl rand -base64 48)
# TESQIVO_BOOTSTRAP_TOKEN=$(openssl rand -hex 24)
docker compose up -d --build
```

`migrate` runs `alembic upgrade head` once and exits; `api` and `worker` wait for
it. Visit `TESQIVO_PUBLIC_URL`, enter the bootstrap token, and create the first
System Admin. After setup, unset `TESQIVO_BOOTSTRAP_TOKEN` and
`docker compose up -d` again.

## Health

- `GET /api/v1/healthz` — liveness (process up).
- `GET /api/v1/readyz` — readiness (database reachable); returns 503 when degraded.
- Compose healthchecks gate `api` on `db` + `migrate`.

## Upgrades

```bash
git pull
docker compose pull        # or rebuild: docker compose build
docker compose up -d       # migrate re-runs; api waits for it
```

Migration compatibility policy: a release never removes a column still read by the
previous minor version. Destructive migrations are split across two releases
(add + backfill, then remove).

## Backup & restore

```bash
make backup
# -> backups/db-YYYYMMDD-HHMMSS.dump  (pg_dump -Fc)
# -> backups/attachments-YYYYMMDD-HHMMSS.tgz

make restore BACKUP=backups/db-XXXX.dump ATTACH=backups/attachments-XXXX.tgz
```

Restore drops and recreates schema objects (`pg_restore --clean --if-exists`),
replaces the attachments volume contents, then re-runs migrations. **Test restore
into a clean environment before relying on it** (acceptance §19.10).

Initial internal targets: RPO 24h, RTO 4h. Schedule `make backup` via cron and
copy `./backups/` off-host.

## Data retention (open — OQ-4)

`user_session`, resolved `background_job`, and import staging files accumulate.
Until a retention policy is set, prune manually:

```sql
DELETE FROM user_session WHERE expires_at < now() - interval '30 days';
```

## Rate limiting (OQ-3)

Phase 1 uses an in-process sliding-window limiter (per client + path class);
auth endpoints are capped tighter. For multi-instance deployments, front with a
shared limiter (reverse proxy or Redis token bucket) — documented as the upgrade
path, not implemented in Phase 1.

## Observability

Structured logs to stdout with `correlation_id`. Every request/response carries
`X-Correlation-ID`. Audit events (`audit_event` table) are append-only and
queryable by authorized users.
