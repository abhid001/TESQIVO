# TESQIVO - Product Requirements Specification

**Version:** 4.0  
**Status:** Architecture baseline  
**Date:** 27 August 2026  
**Supersedes:** `TESQIVO_Product_Requirements_v3.md`

> **Note (2026-09-03):** references to an "open-source" licence in this document are
> historical. Per decision **D-012** (`architecture/16_decisions.md`) the licence is now
> **Proprietary** — see `LICENSE`. §16 "Open-Source Governance" is retained only as a
> record of the earlier plan.

## 1. Purpose and Authority

This document is the product and domain authority for TESQIVO architecture, API design, database design, GUI design, testing, and staged implementation. Where an implementation decision is not covered here, the decision must be recorded before it becomes a cross-module contract.

TESQIVO is an open-source, API-first test management and quality engineering platform. It initially targets self-hosted installation through Docker Compose and may later evolve into a cloud product.

The product connects:

```text
Requirement -> Test Case -> Test Plan -> Test Cycle -> Test Execution -> Defect -> Release evidence
```

### 1.1 Product Vision

TESQIVO is the system of record for software quality. It connects requirements, reusable test assets, planned scope, execution evidence, defects, and release evidence so teams can understand not only whether testing happened, but what was covered, what failed, what remains uncertain, and why a release decision is justified.

The product is intended to make quality information understandable and actionable for the whole delivery team. QA teams manage test assets and execution, developers and automation engineers consume and contribute quality data through APIs, release managers inspect evidence and risk indicators, and auditors can follow changes and decisions through immutable history.

TESQIVO starts as an open-source, self-hosted product for in-house teams. Its architecture must preserve a future path to integrations, AI-assisted test design, and cloud-hosted deployment without allowing those later capabilities to distort the focused Phase 1 product.

### 1.2 Product Differentiators

1. **End-to-end traceability:** Connect requirements to test cases, selected versions, cycles, executions, defects, and releases through structured relationships.
2. **Rich, explainable reporting:** Every metric has a consistent definition, visible scope and freshness, and drill-down to its contributing records.
3. **User-friendly interactive GUI:** Make common test-management workflows efficient, responsive, accessible, and understandable for both specialists and stakeholders.
4. **Strong single and bulk operations:** Apply the same authorization, validation, audit, retry, and domain rules to individual and large-scale actions.
5. **Immutable execution history:** Preserve the exact test version, steps, evidence, result, and correction history used during execution.
6. **API-first automation integration:** Expose documented APIs so CI/CD systems and automation frameworks can use the same domain services as the GUI.
7. **Simple self-hosted deployment:** Make installation, upgrades, persistence, backup, restore, and health behavior practical through Docker Compose.
8. **Human-governed AI assistance:** Later generate test suggestions from requirements, stories, acceptance criteria, and documents while keeping review, approval, privacy, and audit under user and system control.

## 2. Product Principles

- **API first:** Every major GUI action uses a documented backend API. Authorization, validation, workflow, audit, and transaction rules are server-side rules.
- **One domain path:** Single-item, bulk, import, automation, and GUI actions reuse the same domain services.
- **Historical integrity:** Completed execution evidence is immutable and retains the exact test-case version and step content executed.
- **Traceability by design:** Links are structured records with identity, lifecycle, origin, and history.
- **Safe lifecycle:** Archive and soft removal are normal. Permanent deletion is exceptional, explicit, authorized, and audited.
- **Human-governed AI:** AI output is a suggestion or draft and cannot bypass review, authorization, versioning, coverage, or audit rules.
- **Self-hosting is a feature:** Installation, migration, persistence, health, recovery, backup, restore, and secure initialization are product behavior.

## 3. Users and Scope

### 3.1 Users

- System administrators
- Project administrators
- Test managers and QA leads
- Manual testers
- Automation engineers
- Developers
- Release managers
- Auditors and read-only stakeholders

### 3.2 Phases

#### Phase 1 - Self-hosted TCMS and Traceability Foundation

- Local authentication and user management
- Projects, membership, default RBAC, and project reference data
- Hierarchical test repository
- Test-case CRUD, ordered steps, workflow, cloning, versioning, archive, restore, and history
- Test plans, cycles, assignments, version snapshots, and manual execution
- Step-level evidence and immutable execution history
- Lightweight requirements, releases, and defects
- Structured traceability links and a basic interactive traceability matrix
- Design, plan, execution, pass, and defect-impact metrics
- Project, plan, cycle, execution, and traceability dashboards
- Structured filtering, drill-down, and CSV export
- Bulk operations and background jobs
- CSV import and export
- Local attachments
- REST API and generated OpenAPI documentation
- PostgreSQL persistence and Docker Compose deployment
- Audit trail, health checks, backup, restore, and operational hardening

#### Phase 2 - Advanced Quality Engineering

- Rich requirement and defect workflows
- External requirement/defect synchronization
- Automation result API and JUnit XML ingestion
- API tokens, CI/CD guidance, webhooks, and delivery history
- Advanced reports, global search, saved views, and matrix customization
- Graph visualization, path analysis, baseline comparison, and impact analytics
- Excel/PDF formatted exports
- S3-compatible attachment storage and notifications
- Jira, GitLab, GitHub, and Azure DevOps integrations

#### Phase 3 - AI and Advanced Intelligence

- AI test-case generation and coverage-gap suggestions
- Duplicate detection, maintenance, impact analysis, and failure summaries
- Flaky-test, effectiveness, automation-candidate, risk, and release-readiness analytics

#### Phase 4 - Cloud/SaaS

- Organizations, workspaces, tenancy isolation, SSO, subscriptions, cloud storage, Kubernetes, horizontal scaling, and cloud operations

Multi-tenancy, subscriptions, enterprise SSO, external ALM integrations, AI generation, configurable roles/workflows, advanced readiness scoring, Kubernetes, and native mobile apps are excluded from Phase 1.

## 4. Phase Boundary Rules

Phase 1 includes the **Traceability Foundation**. It includes internal Requirement, Release, and Defect records, links, metrics, a basic matrix, drill-down, and CSV export. It does not include synchronization, configurable workflows, graph analytics, saved views, Excel/PDF matrix export, cross-project links, or predictive scoring.

Phase 1 does not calculate a single release-readiness score. It displays factual indicators such as coverage, completion, pass coverage, open critical defects, blocked tests, and data-quality warnings. A readiness conclusion requires a later documented policy.

Phase 3 AI must be anticipated through stable interfaces but must not be implemented as part of the Phase 1 product.

## 5. Domain Model

| Entity | Purpose and ownership |
|---|---|
| Project | Security and configuration boundary for quality data. |
| Project Membership | User, role, and project access; removal revokes future access but preserves history. |
| Reference Value | Project-owned component, release, environment, tag, test type, or attachment policy. |
| Test Folder | Project-owned hierarchy for organizing logical test cases. |
| Test Case | Stable logical identity, metadata, lifecycle, folder, and current/approved version pointers. |
| Test Case Version | Immutable executable content and review status. |
| Requirement | Lightweight Phase 1 business or technical need requiring coverage. |
| Release | Project delivery target to which plans, cycles, requirements, and defects may relate. |
| Test Plan | Testing objective, milestone, release, or regression scope. |
| Test Cycle | Executable plan portion for a release, build, environment, and selected test versions. |
| Cycle Test | One scoped selection in a cycle, with assignment and derived current result. |
| Execution Attempt | One attempt to execute a Cycle Test. |
| Execution Step | Result and evidence for one snapshotted step. |
| Defect | Lightweight Phase 1 failure record linked to evidence and affected scope. |
| Trace Link | Auditable, soft-removable relationship between project entities. |
| Attachment | File associated with a version, execution, or execution step. |
| Audit Event | Append-only record of a significant action. |
| Background Job | Durable asynchronous operation and item-level result record. |

All internal IDs are globally unique UUIDs. Project keys and entity keys are project-unique, readable, immutable, and never reused. Display-name changes do not change identity.

Every project-owned foreign key must reference the same project. Cross-project links are rejected in Phase 1.

## 6. Test Case and Versioning Rules

### 6.1 Ownership Model

The logical `Test Case` owns identity and non-executable organization. `Test Case Version` owns executable content and review status.

A Test Case has:

- one `current_version_id`, which is the newest version;
- zero or one `approved_version_id`, which is the approved version used for new scope; and
- one logical lifecycle state derived from its version and lifecycle events.

A version stores title, description, preconditions, ordered steps, controlled metadata, author, timestamp, version number, status, and change summary. Historical versions are read-only.

### 6.2 Version Creation

Changes to title, description, preconditions, step action, step order, expected result, or other execution-controlled content create a new Draft version. Folder, assignment, tag, and non-controlled organization changes do not create a version but are audited. The controlled-field list is centralized in the domain service.

Editing an Approved or Active test case creates a new Draft version. The previous approved/active version remains available to existing cycles and executions.

### 6.3 Lifecycle

```text
Draft -> In Review -> Approved -> Active -> Deprecated -> Archived
             |             |        |
             +-> Draft     |        +-> Draft (new version on controlled edit)
                           +-> Archived
```

- Draft requires a title and at least one valid step before review.
- Approval applies to the version being reviewed.
- Activation sets the logical test case and selected version active.
- Deprecated tests are excluded from new selection by default but remain available to existing scope and history.
- Archive does not remove cycles, executions, links, attachments, or audit history.
- Restore returns the previous non-archived logical state, or Draft when policy requires re-review.
- Invalid transitions return `409 STATE_TRANSITION_NOT_ALLOWED`.

## 7. Plans, Cycles, Scope, and Execution

### 7.1 Plans

A plan has a project, key, name, description, objective, owner, optional release, status, and audit metadata. A plan may contain a test case at most once. Scope additions are explicit records and may be created manually or from a filter resolved at submission time.

Plan states are `Draft`, `Active`, `Completed`, and `Archived`. A Draft plan needs at least one cycle or scoped test before activation. Completed plans may be reopened by an authorized manager with a reason.

### 7.2 Cycles

A cycle belongs to one plan and has name, description, release, environment, build, optional browser/device/platform, dates, assigned testers, status, and Cycle Test records.

A cycle may contain a test case at most once for a given cycle. If the same logical test must run in multiple environments or builds, create separate cycles. A cycle stores the selected Test Case Version explicitly; later edits, moves, deprecation, or archival of the source Test Case do not change the cycle snapshot.

A Draft cycle may change scope freely. Activation snapshots the approved version for every selected test case. After activation, scope additions/removals are audited. A not-started Cycle Test may be refreshed explicitly by a manager to a newer approved version. A Cycle Test with an In Progress or completed attempt cannot be silently refreshed.

Cycle states are `Draft`, `Active`, `Completed`, `Reopened`, and `Archived`. Activation requires at least one Cycle Test. Completion requires no In Progress attempt. Reopening requires an authorized manager and a reason.

### 7.3 Cycle Test and Attempts

Cycle Test assignment and displayed result are separate from the immutable attempts. A Cycle Test starts as `NOT_RUN`. Its displayed result is derived from its authoritative attempt, or `NOT_RUN` when no attempt exists. `RETEST_PENDING` is an explicit derived indicator when a new attempt has been requested but not completed.

An Execution Attempt captures project, plan, cycle, Cycle Test, selected Test Case Version, immutable step snapshot, release, environment, build, tester, start/end time, duration, overall result, notes, evidence, and defect links.

Attempt states are `IN_PROGRESS`, `PASSED`, `FAILED`, `BLOCKED`, `SKIPPED`, and `ABORTED`. Completed attempts cannot be edited. A manager correction creates an immutable correction event containing old value, new value, actor, reason, and time; it does not rewrite the original attempt evidence.

### 7.4 Result Derivation

Step results are `NOT_RUN`, `PASSED`, `FAILED`, `BLOCKED`, or `SKIPPED`.

Default overall result:

1. Any failed required step -> `FAILED`.
2. Otherwise any blocked required step -> `BLOCKED`.
3. Otherwise all required steps are passed or skipped -> `PASSED`.
4. Otherwise the attempt remains `IN_PROGRESS`.

`SKIPPED` and `ABORTED` are terminal attempt results but are not passing results. An override requires permission and an audited reason.

### 7.5 Authoritative Attempt

For a selected reporting scope, the authoritative attempt is the latest completed attempt ordered by:

1. manager correction timestamp when a correction exists;
2. completion timestamp;
3. immutable attempt ID as a deterministic tie-breaker.

An In Progress attempt is displayed separately and does not replace the latest completed result until completed. Aborted attempts are eligible as the authoritative terminal result. Attempts are compared only within the selected project, cycle, environment, build, release, and other filters.

A retest creates a new attempt and never mutates earlier attempts. Reporting always exposes the authoritative result plus prior-attempt drill-down.

## 8. Requirements, Releases, Defects, and Traceability

### 8.1 Phase 1 Minimum Records

Requirements have immutable key, title, description, type, status, priority, owner, component, optional release, source type, optional external reference, audit fields, and optimistic-concurrency version. Statuses are `Draft`, `Active`, `Fulfilled`, and `Archived`.

Releases have immutable key, name, description, status, dates, owner, optional version label, and audit fields. Statuses are `Planned`, `Active`, `Released`, `Cancelled`, and `Archived`.

Defects have immutable key, summary, description, status, severity, priority, reporter, optional owner/environment/release, detected and resolved build, resolution, source type, optional external reference, audit fields, and optimistic-concurrency version. Statuses are `New`, `Open`, `In Progress`, `Resolved`, `Closed`, and `Rejected`.

Phase 1 supports lightweight lifecycle and fields. Rich configurable workflows and synchronization are Phase 2.

### 8.2 Link Semantics

Trace links are first-class records with:

```text
id, project_id, source_type, source_id, target_type, target_id,
relationship_type, origin, created_by, created_at,
removed_by, removed_at, optional external_reference
```

Supported Phase 1 relationships:

- Requirement -> Test Case
- Requirement -> Release
- Release -> Test Plan
- Release -> Test Cycle
- Test Case Version -> Cycle Test
- Cycle Test -> Execution Attempt
- Execution Attempt -> Defect
- Defect -> Requirement
- Defect -> Release

Requirement links target the logical Test Case. The matrix resolves the link to the Test Case Version selected by the relevant Cycle Test. A link remains valid when a new version is created; the matrix distinguishes the linked logical test from the version planned/executed. Version-specific links may be introduced later if external synchronization requires them.

Duplicate active links are rejected. Links are soft-removed, retain origin and history, and are excluded from normal metrics after removal. Invalid, unresolved, stale, deprecated, and archived links remain visible in data-quality views.

Defect impact follows these supported paths:

```text
Requirement -> Defect
Requirement -> Test Case -> Cycle Test -> Execution Attempt -> Defect
Requirement -> Release -> Defect
```

Execution-mediated impact is valid only when the execution's Cycle Test resolves to a Test Case linked to the Requirement. Drill-down identifies the path.

## 9. Coverage and Reporting Contract

All metrics are calculated by one shared query/service layer. API, GUI, matrix, and exports use the same formula version and return scope, filters, `data_as_of`, numerator, denominator, formula version, and refresh time.

Unless explicitly selected, archived requirements, test cases, releases, plans, cycles, and removed links are excluded. Historical actors and evidence remain visible.

### 9.1 Coverage Policy

- A Requirement is in the denominator when it is Active.
- A Test Case qualifies for design coverage when its current or selected version is Approved or Active. Draft, In Review, Deprecated, and Archived tests do not qualify.
- AI-generated Drafts never qualify until accepted, reviewed, and activated.
- Requirements and tests are mandatory by default. Phase 1 has no optional-test weighting; `Pass Coverage` uses all qualifying in-scope tests. A future optional policy must be a versioned project configuration.
- A skipped test is executed but not passed.
- An aborted test is executed for execution coverage but not passed.
- Empty denominators display `-` and are represented as null in the API, not zero.
- Date filters use the project timezone for boundaries, `[start, end)` semantics, and UTC storage.
- Percentages calculate at full precision and display one decimal place.

### 9.2 Phase 1 Metrics

| ID | Metric | Definition |
|---|---|---|
| M-01 | Scoped tests | Distinct Cycle Tests in selected scope; the same test in different cycles counts separately. |
| M-02 | Execution completion | Terminal Cycle Tests / Scoped Cycle Tests. Terminal means Passed, Failed, Blocked, Skipped, or Aborted. |
| M-03 | Pass rate | Passed / (Passed + Failed + Blocked). Skipped, Aborted, In Progress, and Not Run are excluded. |
| M-04 | Not-run count | Cycle Tests with no current In Progress attempt and no completed attempt. |
| M-05 | Design coverage | Active Requirements with at least one qualifying linked Test Case / Active Requirements. |
| M-06 | Plan coverage | Active Requirements with at least one qualifying linked Cycle Test in selected plan/cycle scope / Active Requirements. |
| M-07 | Execution coverage | Active Requirements with at least one linked scoped Cycle Test with a terminal attempt / Active Requirements. |
| M-08 | Pass coverage | Requirements for which every qualifying in-scope test is Passed / Requirements with at least one qualifying in-scope test. Failed, Blocked, Not Run, In Progress, and all-Skipped fail. |
| M-09 | Requirements uncovered | Active Requirements with zero qualifying linked tests. |
| M-10 | Open critical defects | Distinct Critical Defects not Closed or Rejected. |
| M-11 | Defect-affected requirements | Active Requirements with a direct or supported execution-mediated link to an Open or In Progress Critical/High Defect. |
| M-12 | Automation coverage | Automated active eligible tests / active eligible tests. Not Applicable is excluded; Candidate remains in the denominator. |
| M-13 | Trace-link completeness | Resolvable active links / active links; unresolved external links are reported separately. |

Every metric supports drill-down to its exact contributing records. Reopened cycles use the selected scope and authoritative-attempt rules while retaining prior-attempt history.

## 10. Authorization

Authorization is enforced on every API and domain operation. GUI visibility is not authorization. System Admin has instance-wide access; all other permissions require active project membership.

Default roles:

- **System Admin:** instance users, configuration, and all projects.
- **Project Admin:** project settings, membership, reference data, and project administration.
- **Test Manager:** repository, cases, workflow, plans, cycles, execution correction, requirements, defects, traceability, reports, and permitted bulk actions.
- **Tester:** permitted execution, own/assigned content actions, requirement/defect creation, and permitted links.
- **Viewer:** read-only project data and reports.

The permission service must evaluate concrete conditions for self/assigned operations, not symbolic role labels. Export, bulk actions, audit viewing, API tokens, attachments, and AI capabilities have separate permissions. Archived users remain valid historical actors and cannot obtain new access.

## 11. Bulk Operations and Jobs

Bulk requests contain either explicit IDs or a captured filter, never both. Preview resolves scope, authorization, warnings, and impact without mutation. Confirmation submits the resolved selection and an idempotency key.

Each item is processed with the same authorization and domain validation as a single action. Each item is an independent transaction by default. Related mutations for one item are atomic. Strict import uses one transaction for the complete valid batch and commits nothing if any row fails. Ordinary independent bulk operations allow partial success.

A filter is captured at confirmation time; later records do not enter the job. Permission and validation are evaluated again when each item is processed. Cancellation is best-effort and never rolls back committed items.

Jobs are durable and expose type, creator, scope snapshot, status, progress, counts for requested/resolved/succeeded/failed/skipped/unchanged, item errors, output references, retryability, and timestamps. Statuses are `Queued`, `Running`, `Completed`, `Partially Completed`, `Failed`, and `Cancelled`. Worker leases, idempotency, and item mutation keys prevent duplicate success during retry or worker restart.

## 12. Import, Export, Attachments, and Audit

CSV import is Upload -> Map -> Preview -> Validate -> choose strict/partial -> Confirm -> Results. Stable IDs determine update behavior; duplicate policy is explicit per import. Invalid rows produce a downloadable error file. Import uses normal authorization, versioning, domain services, and audit.

CSV export respects the captured authorized scope. Large exports are jobs with time-limited authorized downloads. Excel and PDF formatted matrix exports are Phase 2.

Attachments belong to Test Case Versions, Execution Attempts, or Execution Steps. Phase 1 uses a persistent local volume. The service enforces allowlisted types, configurable size limits, safe generated names, path protection, parent authorization, upload/deletion audit, and orphan cleanup.

Audit events are append-only and contain event ID, UTC time, actor/system identity, project, entity, action, before/after values where appropriate, source, correlation ID, and parent job ID. Passwords, tokens, secrets, prompts containing sensitive content, and file contents are never logged. Normal APIs cannot update or delete audit records.

## 13. REST API Contract

Base path is `/api/v1`. Resources use plural lowercase nouns. JSON uses UTF-8, `snake_case`, and UTC ISO 8601 timestamps ending in `Z`. UUIDs are used for routes; readable keys are exposed for users.

- `GET` is safe; `PUT` replaces; `PATCH` partially updates.
- `DELETE` soft-removes unless an explicitly protected purge endpoint is introduced.
- Create returns `201` and `Location`; synchronous mutations return `200` or `204`; jobs return `202` and a Job resource.
- Collections return `items`, `page`, `page_size`, `total`, and `links`. Default page size is 25; maximum is 200.
- Repeated values for one filter are OR; different filters are AND. Sorting uses `sort=field,-other_field`.
- Mutable resources expose `ETag` and/or numeric `version`. Critical updates, transitions, and deletes require `If-Match` or `expected_version`.
- Retry-sensitive creates, imports, and ingestion endpoints accept `Idempotency-Key`. Same key and payload returns the original result; a different payload returns `409 IDEMPOTENCY_KEY_REUSED`.
- Requests and responses carry `X-Correlation-ID`.

Errors use:

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "One or more fields are invalid.",
    "status": 422,
    "correlation_id": "01K...",
    "details": [{"field": "/title", "code": "REQUIRED", "message": "Title is required."}],
    "retryable": false
  }
}
```

Stable codes include `AUTHENTICATION_REQUIRED`, `INVALID_CREDENTIALS`, `FORBIDDEN`, `RESOURCE_NOT_FOUND`, `VERSION_CONFLICT`, `STATE_TRANSITION_NOT_ALLOWED`, `DUPLICATE_RESOURCE`, `IDEMPOTENCY_KEY_REUSED`, `VALIDATION_ERROR`, `FILE_TOO_LARGE`, `UNSUPPORTED_MEDIA_TYPE`, `RATE_LIMITED`, `INTERNAL_ERROR`, and `DEPENDENCY_UNAVAILABLE`. Errors never expose stack traces, SQL, secrets, or inaccessible-resource details.

## 14. GUI and Accessibility

The GUI provides stable URLs and navigation for Dashboard, Repository, Plans, Cycles, Executions, Traceability, Reports, Jobs, and Project Settings. It preserves filters and position where practical, distinguishes page selection from all-filtered selection, shows scope and consequences before high-impact actions, and exposes loading, empty, stale, conflict, partial, and error states.

Execution screens support keyboard-friendly step updates, step navigation, evidence, progress, explicit saved/autosaved state, and conflict recovery. Tables support server-side pagination or virtualization, sorting, resizing, export, frozen identifiers, expandable detail, and drill-down.

Core workflows target WCAG 2.1 AA, keyboard access, semantic labels, visible focus, status text/icons in addition to color, and practical desktop/tablet responsiveness. The supported browser baseline is the latest two stable Chrome, Edge, and Firefox versions. A reusable design system defines typography, spacing, controls, tables, statuses, dialogs, notifications, charts, responsive behavior, and accessibility rules.

## 15. Security, Reliability, and Operations

Phase 1 requires adaptive password hashing, secure HttpOnly cookie sessions, configurable expiry, failed-login protection, disabled accounts, password reset, CSRF protection where applicable, rate limits, input sanitization, safe uploads, server-side authorization, dependency/image scanning, and no secrets or stack traces in production output.

Docker Compose includes web UI, API, worker, PostgreSQL, broker, and reverse proxy where required. It provides migrations, readiness and liveness checks, persistent volumes, restart recovery, secure first-admin creation, clear missing-configuration failure, logs, upgrade guidance, backup, restore, and recovery procedures.

Target reference scale is 100 projects, 100,000 test cases in a large project, and 1,000,000 executions per instance. At that reference scale, 95% of ordinary API reads complete within 500 ms server time, ordinary writes within one second excluding files/jobs, bulk requests are accepted within two seconds, and dashboards complete within three seconds or expose cached freshness. These are measured requirements, not assumptions.

PostgreSQL data and attachments are backed up. Restore is tested before production readiness. Initial internal targets are RPO 24 hours and RTO 4 hours. Timestamps are stored in UTC and displayed using the selected/browser timezone.

## 16. Open-Source Governance

Before the first public release, the repository must define:

- an approved open-source license;
- contribution guide and development setup;
- code of conduct;
- security vulnerability reporting and disclosure process;
- issue, feature-request, and bug templates;
- release and semantic-versioning policy;
- supported Docker, PostgreSQL, and browser versions;
- API and migration compatibility policy; and
- deprecation and support policy.

## 17. AI Architecture Boundary - Phase 3

AI generation is a separate asynchronous Generation Job. It reads only sources the requesting user can access and sends content to a configured provider only when instance privacy policy permits it.

The provider is behind an adapter. The domain owns the generation request, source references, structured suggestion schema, review artifact, duplicate/policy checks, acceptance decisions, and audit record. The provider does not write directly to the repository.

A generation result stores model/provider, prompt/template version, source references, generation time, assumptions, ambiguities, token/input limits, and accepting/rejecting user. Suggestions may include test title, preconditions, steps, expected results, priority, type, tags, automation candidacy, rationale, and proposed requirement links.

Workflow:

```text
Authorized source selection -> Generation Job -> Provider adapter
-> validated suggestions -> review workspace -> duplicate/policy checks
-> accepted items become Draft Test Cases -> normal review/approval -> valid coverage
```

The design must address prompt injection in source documents, untrusted content, provider timeout/retry/rate/cost controls, privacy/data residency, partial results, structured-output validation, retention/deletion of prompts and sources, evaluation datasets, quality thresholds, and model/provider failure. AI drafts never count as coverage and cannot overwrite, delete, or silently alter approved tests.

## 18. Feature-Driven Development Increments

Every increment includes migration, domain/service/API behavior, authorization tests, audit behavior, GUI states, automated tests, and updated OpenAPI documentation. It is complete only when acceptance tests pass in Docker Compose.

1. **Deployable shell:** UI/API/PostgreSQL, migrations, health, logs, persistence.
2. **Authentication:** first admin, sessions, login/logout, users, disabled accounts, reset.
3. **Project RBAC:** projects, membership, roles, reference data.
4. **Repository and Draft tests:** folders, ordered steps, CRUD, filters, concurrency.
5. **Versioning and workflow:** review, approval, activation, controlled edits, archive/restore.
6. **Plans and cycles:** scope, assignments, activation snapshots, lifecycle.
7. **Manual execution:** attempts, step results, evidence, derivation, retest, corrections.
8. **Traceability Foundation:** requirements, releases, defects, links, matrix API/UI, metrics.
9. **Dashboards:** shared metrics, filters, drill-down, freshness and data-quality states.
10. **Bulk jobs:** preview, captured scopes, partial results, retries, worker recovery.
11. **Import/export:** CSV mapping, strict/partial behavior, error files, authorized exports.
12. **Operational hardening:** backup/restore, upgrades, security, performance, image/dependency checks.

## 19. Acceptance Criteria

1. A clean supported host starts the application with documented Docker Compose configuration; migrations complete, services become healthy, first-admin setup is secure, and data survives recreation.
2. Every default role passes permitted and forbidden authorization tests; non-members cannot access project data through GUI or API.
3. A user completes Login -> Project -> Repository -> Versioned Test Case -> Plan -> Cycle -> Step Execution -> Dashboard.
4. A controlled edit after execution creates a new version while the completed execution displays the original version and step snapshot.
5. A release with two active requirements, two linked active tests, one passed test, one failed test, and one linked open critical defect produces Design Coverage 100%, Plan Coverage 100%, Execution Coverage 100%, Pass Coverage 0%, Requirements Uncovered 0, Open Critical Defects 1, and Defect-Affected Requirements 1. A separate uncovered requirement fixture verifies 50% coverage values.
6. Matrix and dashboard counts match API and CSV values for identical captured scope and formula version; every count drills down to its contributors.
7. Explicit and filtered bulk selections show preview, captured scope, progress, item results, safe retry, and audit evidence; successful items are not repeated.
8. CSV strict mode commits nothing when invalid rows exist; partial mode commits valid rows and produces item errors.
9. Critical GUI, API, import, bulk, workflow, concurrency, authorization, migration, and audit actions are tested without secrets in logs or responses.
10. Backup and restore recover project data, versions, executions, audit events, links, and attachments in a clean supported environment.
11. Critical automated tests pass and no unresolved Critical/High security issue lacks documented approval.

## 20. Required Design Artifacts

Create and review these artifacts in order before physical schema or production implementation:

1. Product context and actors
2. Navigation and primary user flows
3. Test Case/Test Case Version lifecycle and versioning state diagram
4. Plan, Cycle, Cycle Test, and Execution Attempt state diagrams
5. Traceability relationship model and matrix interaction flow
6. Core logical entity-relationship model, including memberships, links, jobs, audit, and attachments
7. Logical component architecture and service boundaries
8. Docker deployment and persistence diagram
9. Authentication and authorization sequence
10. Manual execution sequence, including snapshot and correction behavior
11. Bulk-job and CSV import sequences, including retry and transaction boundaries
12. Reporting and traceability query flow with metric versioning
13. Phase 2 automation ingestion flow
14. Phase 3 AI generation, review, validation, and approval flow

Every diagram must answer a specific design question, use the domain names in this document, and identify deferred behavior. The domain, state, traceability, and metric artifacts must be reviewed before database tables or implementation code are finalized.

## 21. AI-Assisted Development Rules

An implementation agent must:

1. Treat this document and recorded decisions as scope authority.
2. Keep Phase 1, Phase 2, Phase 3, and Phase 4 behavior separate.
3. Resolve domain invariants and state transitions before database models.
4. Preserve immutable Test Case Versions, snapshots, completed attempts, links, and audit events.
5. Enforce authorization, validation, workflow, concurrency, and audit in backend services.
6. Reuse domain services for GUI, API, import, bulk, and future automation actions.
7. Centralize traceability queries and metric definitions.
8. Use constraints, transactions, migrations, and durable jobs.
9. Keep storage, authentication, integrations, and AI providers behind stable boundaries.
10. Avoid SaaS, AI generation, external synchronization, and predictive scoring in Phase 1.
11. Include automated tests with every increment.
12. Treat Docker installation, upgrade, persistence, backup, restore, and recovery as product features.

## 22. Architecture Freeze Checklist

Architecture may proceed when these artifacts exist and are reviewed:

- Phase boundaries and deferred behavior are consistent with this document.
- Entity/version ownership and snapshot rules are explicit.
- Link targets, defect-impact paths, and cross-project constraints are explicit.
- State transitions and permission conditions are mapped.
- Metric formulas, denominator rules, authoritative-attempt rules, and data-as-of behavior are test-fixture-backed.
- API resource, error, concurrency, idempotency, and bulk contracts are documented.
- Core logical ER model includes history, audit, jobs, attachments, memberships, and link records.
- The Traceability Foundation exit test passes on a representative fixture.
- Open-source license and supported-environment decisions are recorded.
- Remaining open decisions are documented with an owner and decision date.
