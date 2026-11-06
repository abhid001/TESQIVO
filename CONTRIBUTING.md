# Contributing to TESQIVO

Thanks for helping build TESQIVO. This guide covers setup and the rules that keep
the codebase coherent with the product specification.

## Authority

`docs/TESQIVO_Product_Requirements_v4.md` is the product and domain
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

# full stack, built from source (no published image, no .env needed)
make up        # docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
make logs
make down
```

The base `docker-compose.yml` pulls the published `ghcr.io/abhid001/tesqivo` image and is
what self-hosters use. `docker-compose.dev.yml` overrides `web`/`worker` to build from the
root `Dockerfile`; always test through `make up` before opening a PR.

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

## Licensing & the DCO

The Community edition is **AGPL-3.0**; `backend/app/ee/`, `frontend/src/ee/` and
`Dockerfile.enterprise` are proprietary (see `LICENSING.md`). Contributions to the
Community edition are accepted under the
[Developer Certificate of Origin](https://developercertificate.org/) — **sign
every commit** with `git commit -s` (adds a `Signed-off-by:` trailer). Changes
touching `ee/` need a separate agreement; open an issue first.

## Commit / PR conventions

- Conventional-commit style subject (`feat(backend): …`, `fix(web): …`, `docs: …`).
- `Signed-off-by:` trailer on every commit (`git commit -s`).
- Reference the PRS section or increment number where relevant.
- PRs must pass `ci.yml` (lint, backend tests on SQLite + PostgreSQL, migration
  round-trip, frontend typecheck/test/build, an image build, and a Compose smoke boot
  that also runs `create-admin`).

## Versioning & releases

Semantic versioning. API compatibility and migration policy: see `docs/OPERATIONS.md`.

To cut a release:

1. Bump `version` in `backend/pyproject.toml` and `__version__` in
   `backend/app/__init__.py`, and move the `CHANGELOG.md` "Unreleased" notes under the new
   version heading.
2. Merge to `main`, then tag: `git tag v0.2.0 && git push origin v0.2.0`.
3. `.github/workflows/release.yml` builds and pushes the **Community** image
   `ghcr.io/abhid001/tesqivo:{vX.Y.Z, vX.Y, latest}` (multi-arch), then the
   **Enterprise** image `…/tesqivo-enterprise:{same}` on top (`Dockerfile.enterprise`,
   `FROM` the Community image, `TESQIVO_LICENSE_PUBKEY` from the
   `TESQIVO_LICENSE_PUBKEY` repo *variable*). `main` pushes publish `:edge`.
4. **First release only:** set the `tesqivo` GHCR package to *public*; keep
   `tesqivo-enterprise` *private* and grant pull access per customer. Generate the
   license keypair once — see `scripts/license/README.md`.
