# Contributing to TESQIVO

Thanks for helping build TESQIVO. This guide covers setup and the rules that keep
the codebase coherent with the product specification.

## Authority

`project_docs/TESQIVO_Product_Requirements_v4.md` is the product and domain
authority. `docs/architecture/` holds the design artifacts and the decision log
(`16_decisions.md`). Any change that becomes a cross-module contract must be
recorded there before it lands.

## Development setup

Prerequisites: Python 3.12, Node 22, Docker 24+.

```bash
# backend
cd backend && python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest -q
.venv/bin/ruff check app/ tests/

# frontend
cd frontend && npm install && npm run test && npm run typecheck

# full stack
cp .env.example .env   # fill in the two required secrets
docker compose up -d --build
```

## Rules for implementation changes (PRS §21)

1. Keep Phase 1 / 2 / 3 / 4 behaviour separate. Phase 2+ concerns live behind
   interfaces with no Phase 1 implementation.
2. Every write path goes through a domain service in `backend/app/domain/`.
   Routers do transport only.
3. Authorization is checked inside the domain service for every operation, against
   concrete conditions — never role labels alone.
4. Immutable records (`test_case_version` content, cycle-test snapshots, completed
   attempts, trace-link origin, audit events) are never rewritten. Corrections are
   append-only.
5. Mutable aggregate roots carry an integer `version`; critical mutations require
   `expected_version` / `If-Match`.
6. Every project-owned foreign key must reference the same project.
7. Metric definitions and traceability queries live only in
   `app/domain/reporting.py` and `app/domain/traceability.py`.
8. Every increment ships with migrations, tests, and updated OpenAPI. A feature is
   done only when tests pass in Docker Compose.

## Commit / PR conventions

- Conventional-commit style subject (`feat(backend): …`, `fix(web): …`, `docs: …`).
- Reference the PRS section or increment number where relevant.
- PRs must pass `ci.yml` (lint, backend tests on SQLite + PostgreSQL, migration
  round-trip, frontend typecheck/test/build, and a Compose smoke boot).

## Versioning

Semantic versioning. API compatibility and migration policy: see
`docs/OPERATIONS.md`.
