# Changelog

All notable changes to TESQIVO are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- **Enterprise edition scaffolding** (D-021). Proprietary `backend/app/ee/` subtree,
  imported at runtime only when present; a signed Ed25519 `TESQIVO_LICENSE_KEY`
  gates paid features (`app/core/license.py`, `require_feature`, 402
  `LICENSE_REQUIRED`). Two images — public `tesqivo` (Community) and private
  `tesqivo-enterprise` (`Dockerfile.enterprise`). `docker-compose.enterprise.yml`
  overlay, `scripts/license/` tooling, `docs/enterprise.md`.
- `GET /api/v1/version` now reports `edition` and licensed `features`.
- Stub `POST /api/v1/ee/ai/draft-test-case` (real LLM generation lands later).

### Changed
- **Relicensed to open-core**: Community edition is **AGPL-3.0** (`LICENSE`);
  `backend/app/ee/`, `frontend/src/ee/` and `Dockerfile.enterprise` are proprietary
  (`LICENSING.md`). Reverses the interim all-rights-reserved position (D-012).
- Contributions now require a DCO sign-off (`git commit -s`).
- All product-requirements documents moved from `project_docs/` into `docs/`.

## [0.2.0] — 2026-09-01

### Added
- **One-command self-hosting.** A single published image `ghcr.io/abhid001/tesqivo`
  serves the SPA and the API. `docker compose up -d` works with no `.env`.
- `python -m app.cli create-admin` — create the first System Admin from the container
  shell, no bootstrap token required (interactive or `--username/--email/--password`).
- `GET /api/v1/version` reports the running build.
- Auto-generated session secret: when `TESQIVO_SECRET_KEY` is unset the container
  creates one on first boot and persists it in the data volume.
- `docker-compose.tls.yml` optional override for automatic HTTPS via Caddy.
- Release workflow publishes multi-arch images on `v*` tags (and `:edge` on `main`).
- `docs/self-hosting.md`.
- Cycle cloning, a reworked execution runner, and select-all when adding tests to a
  cycle scope.

### Changed
- `docker-compose.yml` now references the published image; building from source moved
  to `docker-compose.dev.yml` (`make up`).
- The one-shot `migrate` service is gone — the image entrypoint applies migrations.
- Migrations `0002`/`0003` are inspector-guarded so the chain applies cleanly on a
  fresh database.
- `.env.example` trimmed: nothing is required for a local trial.

### Removed
- `backend/Dockerfile`, `frontend/Dockerfile` (superseded by the root `Dockerfile`).

## [0.1.0]

- Phase 1 MVP: deployable shell, local auth + first-admin setup, projects & RBAC,
  repository with versioning/review, plans & cycles, manual execution, requirements /
  releases / defects / traceability, the shared reporting layer (M-01…M-13), and the
  React SPA with the admin console.
