# Decision Log

Decisions not fully settled by `TESQIVO_Product_Requirements_v4.md`. Each becomes a
cross-module contract (PRS §1). Format: ID · date · decision · rationale · owner.

| ID | Date | Decision | Rationale | Owner | Status |
|---|---|---|---|---|---|
| D-001 | 2026-08-27 | Backend = Python 3.12 + FastAPI + SQLAlchemy 2.0 async + Alembic + Pydantic v2 | PRS mandates PostgreSQL + generated OpenAPI; team environment is Python (PyCharm); FastAPI generates OpenAPI 3.1 natively | maintainers | accepted |
| D-002 | 2026-08-27 | Background jobs: Redis as queue transport, **PostgreSQL as job state of record** (`background_job`/`job_item`), RQ worker | PRS §11 requires durable jobs, leases, idempotency, item mutation keys — these need transactional storage, not just a broker | maintainers | accepted |
| D-003 | 2026-08-27 | Sessions: opaque 256-bit random id in HttpOnly+Secure+SameSite=Lax cookie, server-side `user_session` table | PRS §15 "secure HttpOnly cookie sessions, configurable expiry"; DB store enables revocation + audit | maintainers | accepted |
| D-004 | 2026-08-27 | Password reset: admin-initiated one-time token (returned in API response / admin UI) is always available. **Superseded in part by D-019** which adds an optional self-service email flow. | Email is not required in Phase 1; PRS lists "password reset" without a delivery channel | maintainers | amended by D-019 |
| D-005 | 2026-08-27 | Reverse proxy + static host = Caddy | Single small binary, automatic TLS, simple `Caddyfile`, serves SPA + proxies `/api` | maintainers | accepted |
| D-006 | 2026-08-27 | Frontend = React 18 + TS + Vite + React Router + TanStack Query + Radix primitives; hand-rolled design system | PRS §14 rich tables, autosave execution, conflict recovery, WCAG 2.1 AA; Radix gives accessible dialogs/menus without a heavy kit | maintainers | accepted |
| D-007 | 2026-08-27 | Metrics computed on-read, no cache table in Phase 1 unless perf tests fail the §15 budgets | Simplicity + correctness first; `report_snapshot` table is a documented fallback | maintainers | accepted |
| D-008 | 2026-08-27 | Controlled-field list is a code constant in `domain/test_case/controlled_fields.py` | PRS §6.2 "centralized in the domain service"; per-project config is a future versioned policy | maintainers | accepted |
| D-009 | 2026-08-27 | Entity keys: `<PROJECT_KEY>-<TYPE>-<seq>`, seq from row-locked `entity_counter` per (project, type), never reused | PRS §5 readable, project-unique, immutable, never reused | maintainers | accepted |
| D-010 | 2026-08-27 | Non-member access to a project resource returns `404 RESOURCE_NOT_FOUND`, not `403` | PRS §13 "Errors never expose ... inaccessible-resource details"; avoids existence disclosure. `403` used when actor IS a member but lacks the specific action. | maintainers | accepted |
| D-011 | 2026-08-27 | CSRF: SameSite=Lax cookie + required custom header (`X-CSRF-Token` double-submit) on unsafe methods | PRS §15 "CSRF protection where applicable"; SPA same-origin via Caddy | maintainers | accepted |
| D-012 | 2026-08-27 | License = Apache-2.0 | Permissive, patent grant, common for infra tooling; PRS §16 requires a decision before first public release | maintainers | proposed — confirm before v1.0 tag |
| D-013 | 2026-08-27 | Supported baseline: Docker 24+, PostgreSQL 16, Redis 7, latest 2 stable Chrome/Edge/Firefox | PRS §14, §16 | maintainers | accepted |
| D-014 | 2026-08-27 | `RETEST_PENDING` is triggered explicitly via `POST /cycle-tests/{id}/retest`; it is a derived display state, not stored | PRS §7.3 describes it as "an explicit derived indicator" | maintainers | accepted |
| D-015 | 2026-08-27 | Attachment storage path: `{ATTACHMENT_DIR}/{project_id}/{parent_type}/{yyyy}/{mm}/{uuid}{ext}`; stored name is a generated UUID, original name kept in DB only | PRS §12 safe generated names, path protection | maintainers | accepted |
| D-016 | 2026-08-27 | A controlled edit to an Approved/Active test case forks a new Draft version but the logical `lifecycle_state` stays Approved/Active; `approved_version_id` still points at the last approved version (used by existing cycles). GUI shows a "draft changes pending review" flag derived from `current_version_id != approved_version_id`. | Keeps design coverage stable while a new version is in progress; consistent with PRS §6.2 "previous approved/active version remains available" | maintainers | accepted |
| D-017 | 2026-08-27 | M-08 Pass Coverage evaluates "every qualifying in-scope test is Passed" across the whole selected scope, not only per-requirement links | Only reading consistent with both numbers stated in acceptance §19.5; see `17_metric_fixtures.md` | maintainers | accepted |
| D-018 | 2026-08-27 | Authoring the test repository (create/edit test cases, folders, workflow) is a Test Manager responsibility; Testers create requirements/defects/links and execute assigned cycle tests, not test cases | PRS §10 "Test Manager: repository, cases, workflow"; Tester line is execution + requirement/defect creation | maintainers | accepted — revisit if teams need tester authoring |
| D-019 | 2026-08-28 | Optional self-service "Forgot password": `POST /auth/password-reset/request {identifier}` behind an optional SMTP mailer (`Mailer` port, `SmtpMailer`/`NullMailer`). When SMTP is unset → response tells the user to contact an administrator. When set → a random temp password is emailed to a matched **non-admin active** account and `must_change_password` is set (forced change screen on next login); non-matches get the same generic message (no existence disclosure). **System-admin accounts always get "contact the maintainer"** and are never emailed — a human must reset them. New `POST /auth/password` lets a signed-in user change their own password. | User request; PRS §15 lists "password reset"; keeps email strictly optional so the zero-config self-hosted path is unchanged | maintainers | accepted |

## Open questions (must have owner + date before Architecture Freeze — PRS §22)

| # | Question | Impact if unresolved |
|---|---|---|
| OQ-1 | Exact duplicate-handling policy wording per import entity (update vs skip vs error) surfaced in UI | Import increment 11 |
| OQ-2 | Whether Phase 1 needs project-level timezone override vs instance default only | Date-boundary metrics §9.1 |
| OQ-3 | Rate-limit thresholds per endpoint class (auth vs read vs write vs bulk) | Security hardening increment 12 |
| OQ-4 | Retention period for `user_session`, resolved `background_job`, import staging files | Ops / storage growth |
| OQ-5 | Confirm Apache-2.0 (D-012) | Governance §16, blocks public release only |
