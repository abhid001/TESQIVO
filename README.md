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

Frontend: React SPA covering Dashboard, Repository, Plans, Cycles, Execution Runner,
Traceability, and Requirements/Defects.

**Handing it to a tester?** See [`docs/TESTING_GUIDE.md`](docs/TESTING_GUIDE.md) —
end-to-end steps to stand it up, create tester accounts, and a suggested walkthrough.

## Quick start (Docker)

```bash
cp .env.example .env
# edit .env: set TESQIVO_SECRET_KEY (openssl rand -base64 48) and
# TESQIVO_BOOTSTRAP_TOKEN (openssl rand -hex 24)

docker compose up -d --build
open http://localhost:8080          # complete first-admin setup with the bootstrap token
```

The stack: `db` (PostgreSQL 16), `redis`, `migrate` (one-shot Alembic), `api`
(FastAPI/Uvicorn), `worker`, `proxy` (Caddy serving the SPA + proxying `/api`).

API docs: `http://localhost:8080/api/v1/docs` · OpenAPI: `/api/v1/openapi.json`.

## Local development

```bash
# backend
cd backend
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q          # 28 tests: smoke, auth, RBAC, versioning, execution, acceptance
.venv/bin/ruff check app/ tests/

# frontend
cd frontend
npm install
npm run test          # vitest
npm run typecheck
npm run dev           # proxies /api to localhost:8000
```

Run the API against a local Postgres:

```bash
export TESQIVO_DB_URL=postgresql+asyncpg://tesqivo:tesqivo@localhost/tesqivo
export TESQIVO_REDIS_URL=redis://localhost:6379/0
export TESQIVO_SECRET_KEY=dev-secret-that-is-at-least-32-bytes-long
export TESQIVO_PUBLIC_URL=http://localhost:8000
export TESQIVO_BOOTSTRAP_TOKEN=dev-token
cd backend && alembic upgrade head && uvicorn app.main:app --reload
```

## Backup / restore

```bash
make backup                                   # → ./backups/
make restore BACKUP=backups/db-XXXX.dump ATTACH=backups/attachments-XXXX.tgz
```

## License

Apache-2.0 (proposed — see decision D-012). See [LICENSE](LICENSE).
