# TESQIVO

Open-source, API-first test management and quality engineering platform.
Self-hosted via Docker Compose. See
[`project_docs/TESQIVO_Product_Requirements_v4.md`](project_docs/TESQIVO_Product_Requirements_v4.md)
for the product specification and [`docs/architecture/`](docs/architecture/) for the
design artifacts (14 diagrams, decision log, metric fixtures).

```
Requirement → Test Case → Test Plan → Test Cycle → Test Execution → Defect → Release evidence
```

## Status — Phase 1 MVP

This repository implements the **Phase 1 vertical slice** (PRS §18 increments 1–9):

| Increment | Area | State |
|---|---|---|
| 1 | Deployable shell (health, OpenAPI, config, errors, correlation, rate limit) | ✅ implemented + tested |
| 2 | Local authentication, first-admin setup, sessions, lockout, reset | ✅ |
| 3 | Projects, membership, default RBAC, reference data | ✅ |
| 4–5 | Repository, folders, steps, versioning, review/approve/activate workflow | ✅ |
| 6 | Plans, scope, cycles, activation snapshot | ✅ |
| 7 | Manual execution, derivation, authoritative attempt, retest, corrections | ✅ |
| 8 | Requirements / releases / defects, trace links, traceability matrix | ✅ |
| 9 | Shared reporting layer, metrics M-01…M-13, CSV export, dashboards | ✅ |
| 10 | Bulk jobs (preview / captured scope / retries / worker recovery) | 🟡 worker + job model scaffolded; bulk endpoints pending |
| 11 | CSV import (map / validate / strict-partial / error files) | 🟡 sequence designed (`docs/architecture/12`), not implemented |
| 12 | Operational hardening (backup/restore automation test, image scan, perf) | 🟡 `make backup`/`restore` + Compose; automated restore test pending |

Frontend: React SPA covering Dashboard, Requirements, Plans, Scenarios, Tests,
Releases, Cycles, Execution Runner, and Traceability — plus an admin console
(users, projects, access requests, feedback), self-service project discovery /
access requests, per-user profile, and an always-on feedback channel.

**Handing it to a tester?** See [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) —
end-to-end steps to stand it up, create tester accounts, and a suggested walkthrough.

## Quick start (Docker)

```bash
curl -O https://raw.githubusercontent.com/abhid001/TESQIVO/main/docker-compose.yml
docker compose up -d
docker compose exec web python -m app.cli create-admin
# open http://localhost:8080
```

No `.env` is required for a trial. One image (`ghcr.io/abhid001/tesqivo`) serves the
SPA and the API; `db` (PostgreSQL 16) and `redis` run alongside it.

**Installing it somewhere real?** [`INSTALL.md`](INSTALL.md) is a complete,
self-contained guide — prerequisites, config, HTTPS, upgrades, backup/restore,
troubleshooting. Deeper operational detail is in [`docs/self-hosting.md`](docs/self-hosting.md).

API docs: `http://localhost:8080/api/v1/docs` · OpenAPI: `/api/v1/openapi.json` ·
build: `/api/v1/version`.

## Local development

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check app/ tests/

# frontend
cd frontend
npm install
npm run test          # vitest
npm run typecheck
npm run dev           # proxies /api to localhost:8000
```

Run the API against a local Postgres (a session secret is generated automatically):

```bash
export TESQIVO_DB_URL=postgresql+asyncpg://tesqivo:tesqivo@localhost/tesqivo
export TESQIVO_REDIS_URL=redis://localhost:6379/0
export TESQIVO_PUBLIC_URL=http://localhost:8000
export TESQIVO_SECRET_KEY_FILE=./.tesqivo-secret
cd backend && alembic upgrade head && uvicorn app.main:app --reload
```

Full stack from source (builds the image locally):

```bash
make up        # docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
```

## Backup / restore

```bash
make backup                                   # → ./backups/
make restore BACKUP=backups/db-XXXX.dump ATTACH=backups/appdata-XXXX.tgz
```

## License

Apache-2.0 (proposed — see decision D-012). See [LICENSE](LICENSE).
