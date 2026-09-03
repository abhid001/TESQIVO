# TESQIVO — Refined Product Requirements Specification

**Version:** 2.0  
**Status:** Baseline for diagrams and architecture  
**Date:** 26 August 2026  

## 1. Purpose

This specification defines what TESQIVO must deliver before detailed diagrams and development begin. It separates mandatory MVP scope from later capabilities and establishes the domain rules that architecture, APIs, database design, GUI design, and testing must follow.

## 2. Product Vision

TESQIVO is an API-first Test Management and Quality Engineering platform that acts as the **system of record for software quality**.

It must connect the lifecycle:

> Requirement → Test Case → Test Plan → Test Cycle → Test Execution → Defect → Release Readiness

TESQIVO will first support in-house, self-hosted installation through Docker Compose and later evolve into a cloud-hosted product.

### 2.1 Primary Product Differentiators

1. **End-to-end test traceability** with an interactive traceability matrix
2. **Rich, drill-down reporting** with consistent metric definitions
3. **User-friendly, responsive, and interactive GUI**
4. Strong single-item and bulk operations
5. Immutable execution history and complete auditability
6. API-first automation integration
7. Simple self-hosted deployment
8. Later-stage, human-governed AI test-case generation

### 2.2 Target Users

- System and project administrators
- QA leads and test managers
- Manual testers
- Automation engineers
- Developers
- Release managers
- Auditors and read-only stakeholders

## 3. Product Principles

### P-01 — API First

Every major GUI action must use a documented backend API. Authorization, validation, workflow, audit, and transaction rules must be enforced on the server.

### P-02 — Shared Single and Bulk Logic

Single and bulk actions must use the same domain services. Bulk processing must not bypass rules that apply to an individual record.

### P-03 — Historical Integrity

Editing a test case must never alter completed execution evidence. Executions must retain the exact test-case version and step content that were executed.

### P-04 — Traceability by Design

Traceability links must be structured domain relationships, not text conventions or report-only calculations.

### P-05 — Safe Data Lifecycle

Archive and soft delete are the normal removal mechanisms. Permanent deletion must be restricted, explicit, and audited.

### P-06 — Human-Governed AI

AI-generated content must enter TESQIVO as a suggestion or draft. It cannot silently overwrite approved test assets, create misleading coverage, or bypass review, authorization, versioning, and audit rules.

### P-07 — Self-Hosting as a Product Feature

Docker deployment must include initialization, migrations, persistence, health checks, restart recovery, backup guidance, and secure first-admin creation.

## 4. Scope and Roadmap

### 4.1 Phase 1 — Self-Hosted TCMS MVP

- Local authentication and user management
- Projects, membership, and default RBAC roles
- Hierarchical test repository
- Test-case CRUD, steps, workflow, cloning, versioning, archive, and restore
- Strong single and bulk test-case actions
- Test plans and test cycles
- Manual execution and step-level evidence
- Immutable execution snapshots and execution history
- Project, plan, cycle, and execution dashboards
- Structured filters and interactive drill-down
- CSV import and export
- Audit trail
- Background jobs for large operations
- Local file attachments
- REST API for every major MVP operation
- PostgreSQL persistence
- Docker Compose installation

### 4.2 Phase 2 — Traceability and Quality Engineering

- Internal requirements or synchronized external requirements
- Lightweight internal defects or synchronized external defects
- End-to-end traceability graph and flagship traceability matrix
- Advanced reports, saved views, and global search
- Automation result API and JUnit XML ingestion
- CI/CD integration guidance and API tokens
- Webhooks and delivery history
- Jira, GitLab, and Azure DevOps integrations
- S3-compatible attachment storage
- In-app and email notifications

**Important:** Phase 1 must preserve requirement and defect extension points, but their full modules must not delay the first usable release. Traceability UX, data relationships, and metric definitions must be designed during the initial architecture phase because they are central to TESQIVO.

### 4.3 Phase 3 — AI and Advanced Intelligence

- AI test-case generation from requirements, user stories, API specifications, and selected documents
- AI suggestions for missing scenarios, negative cases, boundaries, and coverage gaps
- Duplicate and near-duplicate test detection
- AI-assisted test maintenance and impact analysis
- Failure summaries and probable failure grouping
- Automation candidate recommendations
- Flaky-test and test-effectiveness analytics
- Configurable release-readiness scoring
- Risk-based regression recommendations

### 4.4 Phase 4 — Cloud / SaaS

- Organizations and workspaces
- Multi-tenancy and tenant isolation
- SSO providers
- Subscription and usage management
- Cloud storage
- Kubernetes deployment and horizontal scaling
- Tenant-level security and configuration
- Cloud observability, rate limiting, backup, and disaster recovery

### 4.5 Explicit MVP Exclusions

- Multi-tenancy and subscriptions
- Enterprise SSO
- AI generation and predictive scoring
- External ALM integrations
- Fully configurable roles, workflows, and dashboard layouts
- Kubernetes deployment
- Native mobile applications

## 5. Core Domain Model

| Entity | Purpose |
|---|---|
| Project | Security and configuration boundary for quality data. |
| Test Folder | Hierarchical organization inside a project. |
| Test Case | Reusable test definition and metadata. |
| Test Case Version | Immutable test content at a point in time. |
| Requirement | Business or technical need requiring coverage. |
| Test Plan | Testing objective, release, milestone, or regression scope. |
| Test Cycle | Executable portion of a plan for a build and environment. |
| Cycle Test | Selected test-case version, assignment, and current state. |
| Execution | One attempt to run a cycle test. |
| Execution Step | Result and evidence for a snapshotted test step. |
| Defect | Failure record linked to evidence and affected scope. |
| Release | Project delivery target. |
| Audit Event | Immutable record of a significant action. |
| Background Job | Asynchronous bulk, import, export, or report operation. |

### 5.1 Identifier Rules

- Internal IDs must be globally unique.
- Project keys are unique and immutable.
- Test cases use readable IDs such as `PAY-TC-101`.
- Plans, cycles, executions, requirements, and defects should use typed readable IDs.
- Deleted identifiers must never be reused.
- Display-name changes must not change identifiers.

### 5.2 Relationship Rules

- Project-owned entities cannot be linked across projects unless a later feature explicitly supports it.
- A test case has one current version and immutable historical versions.
- A plan contains one or more cycles.
- A cycle stores the selected test-case version.
- A cycle test may have multiple execution attempts.
- Completed attempts remain immutable except for an audited manager correction.
- Requirements and defects must connect through structured links that retain source and history.

## 6. Authentication and Authorization

### 6.1 MVP Authentication

- Username or email plus password
- Secure password hashing
- Login, logout, and password change
- Administrator-initiated password reset
- Configurable session expiry
- Failed-login protection
- Disabled accounts
- Secure, documented first-System-Admin creation

### 6.2 Default Roles

| Role | Scope | Capability |
|---|---|---|
| System Admin | Instance | Users, configuration, and all projects |
| Project Admin | Project | Project settings and membership |
| Test Manager | Project | Repository, cases, plans, cycles, and reports |
| Tester | Project | Assigned and permitted executions |
| Viewer | Project | Read-only project access |

Authorization must be enforced on every protected API. A non-member must not access project data by manipulating a URL or request. Archived users remain visible in historical records.

## 7. Project and Repository Requirements

### FR-PRJ-01 — Projects

Authorized users can create, update, archive, and restore projects. Required fields are name, immutable key, description, owner, status, and audit metadata.

### FR-PRJ-02 — Membership

Project Admins can add active users, assign/change roles, and remove membership. Removal revokes future access without deleting historical assignments or authorship.

### FR-PRJ-03 — Reference Data

Projects configure components, releases, environments, tags, test types, and permitted attachment policies. Values already in use must be archived rather than hard-deleted.

### FR-REP-01 — Folder Hierarchy

Authorized users can create, rename, move, archive, and restore folders. TESQIVO must prevent circular hierarchies, cross-project movement, and moves into a descendant.

## 8. Test-Case Management

### 8.1 Core Fields

- Readable ID and title
- Description and preconditions
- Ordered steps with action and expected result
- Priority: Critical, High, Medium, Low
- Test type
- Automation status: Manual, Candidate, Automated, Not Applicable
- Workflow status
- Owner and reviewer
- Folder, component, and tags
- Requirement links when Phase 2 is enabled
- Attachments
- Version and created/updated metadata

Severity belongs primarily to defects and execution failures. It may be optional test-case metadata but must not be mandatory in the MVP.

### FR-TC-01 — Lifecycle

Authorized users can create, edit, clone, move, review, approve, activate, deprecate, archive, restore, and inspect history.

Recommended workflow:

> Draft → In Review → Approved → Active → Deprecated → Archived

Editing an Approved or Active test case creates a new Draft version. The previously approved version remains available for existing cycles and execution history.

### FR-TC-02 — Versioning

A version is created when execution meaning changes, including title, description, preconditions, step action/order/expected result, or other controlled content. Assignment, folder, and tag changes may remain audit-only. The trigger policy must be centralized.

Each version stores content, version number, author, timestamp, status, and change summary. Historical versions are read-only.

### FR-TC-03 — Cycle Selection

When a cycle is activated, it stores the selected approved/current test-case versions. A manager may refresh a not-started cycle test to a newer version. Started or completed attempts cannot be silently refreshed.

## 9. Single and Bulk Operations

### 9.1 MVP Bulk Actions

- Change priority, owner, component, or automation status
- Add or remove tags
- Move folder
- Clone
- Archive or restore
- Add to or remove from a plan
- Export

### 9.2 Required Behavior

- Users can select explicit rows or all results matching a filter.
- A confirmation view displays action, filters, resolved count, and impact.
- Every target receives the same authorization and validation as a single action.
- Large operations run asynchronously above a configurable threshold.
- Results show total, succeeded, failed, and skipped counts with item-level reasons.
- Retrying failures must not repeat successful mutations.
- Requests must be protected against accidental duplicate processing.
- Every job and item change is auditable.
- Independent records default to partial success; import also offers strict all-or-nothing mode.

Bulk permanent deletion is excluded from ordinary user workflows.

## 10. Plans, Cycles, and Executions

### FR-PLAN-01 — Test Plans

A plan represents a release, feature, milestone, or regression objective. Users can create, edit, clone, archive, associate a release, add test cases manually or through filters, assign an owner, and view progress.

Statuses: Draft, Active, Completed, Archived.

### FR-CYCLE-01 — Test Cycles

A cycle includes name, description, environment, release, build, optional browser/device/platform, dates, assigned testers, selected test versions, and status.

Statuses: Draft, Active, Completed, Reopened, Archived.

Only Draft cycles freely change scope. Scope changes after activation are audited. Completed cycles are read-only unless reopened by a permitted user with a reason.

### FR-EXEC-01 — Execution Attempts

Every attempt captures project, plan, cycle, release, environment, build, tester, immutable test-case snapshot, start/end time, duration, overall result, step results, notes, evidence, and linked defects where enabled.

Attempt statuses:

- IN_PROGRESS
- PASSED
- FAILED
- BLOCKED
- SKIPPED
- ABORTED

`NOT_RUN` describes a cycle test before an attempt exists.

### FR-EXEC-02 — Step-Level Result

Each step supports NOT_RUN, PASSED, FAILED, BLOCKED, or SKIPPED, plus actual result, comments, evidence, and completion time.

Default overall result:

1. Any failed step → FAILED
2. Otherwise any blocked step → BLOCKED
3. Otherwise all required steps passed or skipped → PASSED
4. Otherwise → IN_PROGRESS

Overrides require permission and an audited reason. Retesting creates a new attempt. Completed attempts are locked; manager correction preserves the old value and reason.

### FR-EXEC-03 — Concurrent Editing

TESQIVO must prevent silent overwrites through optimistic concurrency or equivalent checks. Stale updates receive a conflict response.

## 11. Traceability — Flagship Capability

Traceability must answer:

- Which test cases cover a requirement?
- Which requirements have no, incomplete, or outdated coverage?
- Which test version was planned and executed?
- Which tests have not run for a selected release, cycle, or environment?
- Which failures and defects affect a requirement or release?
- What evidence supports a release-readiness conclusion?

### FR-TRC-01 — Link Types

The model must support:

- Requirement ↔ Test Case
- Requirement ↔ Release
- Test Case Version ↔ Plan/Cycle
- Cycle Test ↔ Execution Attempt
- Execution ↔ Defect
- Defect ↔ Requirement/Release

Each link stores its creator/source, creation time, status, and external reference where applicable.

### FR-TRC-02 — Interactive Traceability Matrix

The matrix must provide:

- Rows by requirement with expandable test cases and executions
- Configurable columns for plan, cycle, release, environment, latest result, defects, owner, priority, and coverage
- Filters for project, release, component, requirement status/type, test status/type, environment, build, and date
- Frozen headers/identifier columns, sorting, resizing, pagination or virtualization
- Expand/collapse, hover details, and direct navigation to source records
- Color plus text/icons so status is not color-dependent
- Drill-down from every count to the contributing records
- Saved views in Phase 2
- CSV/Excel export of the filtered matrix
- Clear handling of missing, stale, unmapped, and conflicting data

### FR-TRC-03 — Coverage Definitions

Central definitions must distinguish:

- **Design coverage:** requirement has at least one active linked test case
- **Plan coverage:** requirement has at least one linked test in selected plan/cycle scope
- **Execution coverage:** requirement has at least one completed execution in selected scope
- **Pass coverage:** required in-scope tests satisfy the configured passing rule

Coverage must not count an AI-generated Draft as valid design coverage until a user reviews and activates it.

### FR-TRC-04 — Freshness

Traceability views display calculation time and selected scope. Links to deprecated tests, obsolete requirement versions, stale executions, or archived records must be visibly distinguished rather than silently ignored.

## 12. Dashboards and Rich Reporting

### FR-RPT-01 — MVP Dashboards

Provide project, plan, and cycle dashboards with:

- Total scoped tests
- Not run, in progress, passed, failed, blocked, and skipped
- Execution completion and pass rate
- Results by cycle, tester, component, environment, and build
- Recent activity
- Top failures and blocked areas
- Direct drill-down to filtered records

### FR-RPT-02 — Phase 2 Reports

- Traceability matrix and requirement coverage
- Release execution summary
- Failure analysis
- Defect summary and leakage
- Automation coverage
- Execution and pass-rate trends
- Tester workload
- Test inventory, aging, and reusability
- Audit report

Phase 3 adds flaky-test, effectiveness, risk, and release-readiness reports.

### 12.1 Central Metric Definitions

| Metric | Default definition |
|---|---|
| Execution completion | `(Passed + Failed + Blocked + Skipped) / Total scoped cycle tests × 100` |
| Pass rate | `Passed / (Passed + Failed + Blocked) × 100` |
| Not run | Scoped cycle tests without a completed or current in-progress attempt |
| Automation coverage | `Automated active tests / Active automation-eligible tests × 100` |

Metrics must define scope, zero-denominator behavior, archive handling, authoritative attempt, date/time zone, and refresh timestamp. GUI, API, and exports must use the same definitions.

### FR-RPT-03 — Interactive Reporting

- Global filters apply consistently to compatible widgets.
- Clicking any metric or chart segment opens its contributing records.
- Users can switch table/chart views where meaningful.
- Tables support sorting, column selection, resizing, pagination/virtualization, and export.
- Long calculations run as background jobs with visible progress.
- Empty, loading, stale, error, and partial-data states are explicit.

## 13. GUI and User Experience

### UX-01 — Navigation

The GUI must provide consistent navigation for Dashboard, Repository, Plans, Cycles, Executions, Traceability, Reports, Jobs, and Project Settings. Breadcrumbs and stable URLs must make deep pages understandable and shareable.

### UX-02 — Efficient Workflows

- Common actions are available without excessive page changes.
- List views preserve filters and position after record updates where practical.
- Inline editing may be used only when validation and audit behavior remain clear.
- Bulk selection clearly differentiates selected page rows from all filtered results.
- Destructive or high-impact actions show scope, consequence, and confirmation.
- Forms preserve unsaved work or warn before navigation.
- Success and error messages state what happened and what the user can do next.

### UX-03 — Interactive Execution

Execution screens should provide step navigation, keyboard-friendly status updates, evidence upload, clear remaining-step progress, autosave or explicit saved state, and conflict handling.

### UX-04 — Accessibility and Responsiveness

- Target WCAG 2.1 AA for core workflows.
- Keyboard-accessible navigation and controls
- Visible focus indicators and semantic labels
- Status not communicated by color alone
- Desktop-first responsive layout with practical tablet support
- Latest two stable Chrome, Edge, and Firefox versions supported

### UX-05 — Performance Perception

Use skeleton/loading states, progressive rendering, pagination or virtualization, optimistic feedback only when safe, and non-blocking background progress. The GUI must never appear frozen during bulk or reporting work.

### UX-06 — Design System

A reusable design system must define colors, typography, spacing, buttons, forms, tables, badges, status icons, dialogs, notifications, charts, accessibility behavior, and responsive rules. The same status must use consistent labels and visual treatment across the application.

## 14. Import, Export, and Attachments

### FR-IMP-01 — CSV Import

Flow: Upload → Map columns → Preview → Validate → Choose strict/partial mode → Confirm → Review results.

- Strict mode commits only if all rows are valid.
- Partial mode commits valid rows and reports invalid rows.
- Duplicate behavior is explicit: skip, update by stable ID, or create.
- The result provides success/warning/error counts and a downloadable error file.
- Import uses normal authorization, validation, versioning, and audit services.

Excel may follow CSV once the behavior is stable.

### FR-EXP-01 — Export

Selected or filtered authorized data can be exported to CSV; Phase 2 adds Excel where valuable. Large exports are background jobs with time-limited authorized downloads.

### FR-ATT-01 — Attachments

Files may belong to test-case versions, executions, and execution steps. TESQIVO must enforce configurable size/type limits, safe names, path protection, parent authorization, upload/deletion audit, and orphan cleanup. Phase 1 uses persistent local storage; Phase 2 adds S3-compatible storage.

## 15. Audit Trail and Background Jobs

### FR-AUD-01 — Audit Events

Capture event ID, UTC time, actor/system identity, project, entity, action, relevant before/after values, source, correlation ID, and parent bulk-job ID. Passwords, tokens, secrets, and file contents must never be logged.

Audit user/security, project/member, case/version/workflow, plan/cycle, execution/correction, import/export/bulk, attachment, permission, and configuration changes. Audit records are append-only through normal APIs.

### FR-JOB-01 — Background Processing

Jobs expose type, creator, scope, creation time, status, progress, success/failure/skipped counts, item-level errors, outputs, and retries.

Statuses: Queued, Running, Completed, Partially Completed, Failed, Cancelled.

Jobs must survive worker restart, be safe against duplicate delivery, and avoid duplicating successful changes during retry.

## 16. REST API

- Versioned path, initially `/api/v1`
- JSON except file transfers
- Consistent resources and error schema
- Pagination, filtering, sorting, and structured search parameters
- Authentication and project authorization
- UTC ISO 8601 timestamps
- Correlation/request IDs
- Optimistic concurrency on critical updates
- Idempotency for harmful duplicate creates and ingestion retries
- Generated OpenAPI documentation

Errors include a stable code, readable message, field errors, and correlation ID without stack traces or secrets.

## 17. AI Test-Case Generation — Phase 3

### AI-01 — Supported Inputs

AI generation may accept:

- Internal or synchronized requirements and user stories
- Acceptance criteria
- OpenAPI/Swagger specifications
- Selected text documents
- Existing related test cases and project testing standards

### AI-02 — Generated Output

AI may propose:

- Test-case title, description, and preconditions
- Positive, negative, boundary, validation, security, API, UI, and data scenarios as relevant
- Ordered steps and expected results
- Suggested priority, type, component, tags, and automation candidacy
- Source requirement links and generation rationale
- Assumptions, ambiguities, and missing-information warnings

### AI-03 — Review Workflow

1. User selects source and generation preferences.
2. TESQIVO creates a generation job.
3. AI output appears in a review workspace, not the active repository.
4. User compares suggestions, edits fields, rejects duplicates, and selects items.
5. Accepted items are created as Draft test cases.
6. Normal review/approval activates coverage.

### AI-04 — Governance and Safety

- AI output is visibly labeled as generated or assisted.
- Model/provider, generation time, source references, prompt/template version, and accepting user are audited.
- Source access uses the requesting user’s permissions.
- Sensitive project content is not sent to a provider unless that provider/configuration is authorized.
- Users can reject, edit, regenerate, or accept individual suggestions.
- AI cannot delete or overwrite approved test cases automatically.
- AI drafts do not count toward valid coverage until reviewed and activated.
- Duplicate detection runs before acceptance.
- Provider integration uses an abstraction so the core domain is not tied to one AI service.

### AI-05 — Quality Measurement

Track acceptance rate, edit distance, duplicate rate, reviewer feedback, requirement coverage contribution after approval, and defects later associated with accepted AI-created tests. These metrics evaluate usefulness; they must not be presented as proof that AI output is correct.

## 18. Self-Hosted Deployment

The supported Docker Compose package initially includes web UI, backend API, background worker, PostgreSQL, Redis or equivalent broker, and reverse proxy where required.

A documented clean installation must support:

```bash
docker compose up -d
```

and provide:

- Database readiness and automated migrations
- Persistent volumes
- Health checks and restart behavior
- Secure initial administrator setup
- Clear failure for missing mandatory configuration
- Installation, upgrade, logs, backup, restore, and recovery guidance

Configuration and secrets are externalized. Secrets must not be committed, logged, or exposed to the frontend.

## 19. Non-Functional Requirements

### Performance

- 95% of ordinary API reads complete within 500 ms server time in the reference environment.
- 95% of ordinary creates/updates complete within 1 second, excluding file transfer/background work.
- Lists use server-side pagination and support at least 100,000 test cases in a large project.
- Background bulk requests are accepted within 2 seconds.
- Dashboard summaries complete within 3 seconds or show cached freshness.
- Large traceability tables use server-side querying plus pagination or virtualization.

### Reliability and Integrity

- Committed data survives service/container restart.
- Database constraints enforce relationships and project boundaries.
- Accepted jobs recover after worker restart.
- Migrations are versioned, repeatable, and upgrade-tested.
- Timestamps are stored in UTC and displayed in the selected/browser time zone.

### Security

- Current adaptive password hashing
- Server-side authorization with negative tests
- Protection against common injection, scripting, request-forgery, access-control, and unsafe-upload risks
- Secure cookie settings when cookies are used
- Rate limiting of login and sensitive endpoints
- Dependency and image scanning in CI
- No secrets or stack traces in production output

### Maintainability and Observability

- Modular boundaries and database migrations
- Unit, integration, API, authorization, migration, and end-to-end tests
- CI formatting, linting, tests, vulnerability checks, and image build
- Structured logs and correlation IDs
- API, worker, database-dependency, and readiness health endpoints

### Backup and Recovery

Backup covers PostgreSQL and attachments. Restore must be tested before production readiness. Initial proposed internal targets are RPO 24 hours and RTO 4 hours.

## 20. MVP Acceptance Criteria

1. **Installation:** A clean host starts TESQIVO through documented Docker Compose configuration; migrations finish, services become healthy, admin setup is secure, and data persists after recreation.
2. **Authorization:** Every default role passes permitted checks and fails forbidden checks; non-members cannot access project data via GUI or API.
3. **Vertical slice:** A user completes Project → Repository → Versioned Test Case → Plan → Cycle → Step Execution → Dashboard.
4. **History:** Editing an executed test creates a new version while the execution shows the exact older snapshot.
5. **Bulk actions:** Explicit and filtered selections provide preview, progress, partial results, errors, safe retry, and audit evidence.
6. **Reporting:** Dashboard numbers match centralized formulas and every count drills into the same contributing records.
7. **GUI:** Core workflows pass keyboard, responsive-layout, validation, loading/error-state, and usability acceptance checks.
8. **Import/export:** CSV strict and partial modes behave as documented; exported scope matches authorized source data.
9. **Audit:** Critical UI, API, import, and bulk changes record complete audit events without secrets.
10. **API parity:** Every major MVP GUI action uses a documented application API.
11. **Recovery:** A backup restores project data, versions, executions, audit events, and attachments into a clean supported environment.
12. **Quality gate:** Critical automated tests pass and no unresolved Critical/High security issue lacks documented approval.

## 21. Decisions Required Before Architecture Freeze

| ID | Decision | Recommended starting point |
|---|---|---|
| D-01 | Frontend/backend technologies | Choose for team capability; preserve API boundary. |
| D-02 | Web authentication transport | Secure server-side session with HttpOnly cookie. |
| D-03 | Excel import in MVP | CSV first; `.xlsx` only for an initial-adopter need. |
| D-04 | Approval workflow in MVP | Include basic workflow if review/approval is required internally. |
| D-05 | Version selection | Snapshot current approved version at cycle activation. |
| D-06 | Authoritative execution | Latest completed attempt; manager can select another with reason. |
| D-07 | Background-job threshold | Configurable; initial proposal 500 records. |
| D-08 | Attachment limit | Configurable; initial proposal 25 MB/file plus allowlist. |
| D-09 | Reference scale | 100 projects, 100,000 cases/large project, 1,000,000 executions/instance. |
| D-10 | Requirement strategy | Internal records plus external references, then provider synchronization. |
| D-11 | Defect strategy | Lightweight internal defect plus external-provider links. |
| D-12 | AI provider policy | Provider abstraction with instance-level data/privacy configuration. |

## 22. Required Diagram Set

Create diagrams in this order:

1. Product context and actor diagram
2. Core navigation and user-flow map
3. Test-case lifecycle/versioning state diagram
4. Plan, cycle, and execution state diagrams
5. Traceability relationship model and matrix interaction flow
6. Core entity-relationship diagram
7. Logical component architecture
8. Docker deployment diagram
9. Authentication/authorization sequence
10. Manual execution sequence
11. Bulk-job and import sequences
12. Reporting and traceability query flow
13. Phase 2 automation-ingestion flow
14. Phase 3 AI generation, review, and approval flow

Domain, state, and traceability diagrams must be reviewed before database tables or implementation code are finalized.

## 23. AI-Assisted Development Rules

Before generating code, an AI development model must:

1. Treat this specification and confirmed decisions as scope authority.
2. Separate MVP requirements from later phases.
3. Resolve domain invariants and states before database models.
4. Preserve immutable versions, execution snapshots, and audit records.
5. Enforce authorization, validation, workflow, and audit in backend services.
6. Reuse domain services for UI, API, import, automation, and bulk actions.
7. Centralize traceability and reporting definitions.
8. Use database constraints, transactions, and migrations.
9. Keep storage, authentication, integrations, and AI providers behind stable boundaries.
10. Avoid implementing SaaS, AI, or advanced analytics in the MVP.
11. Include automated tests with each feature.
12. Treat Docker install, upgrade, persistence, backup, and restore as product features.

## 24. Immediate Development Goal

The first goal is a reliable self-hosted vertical slice:

> Login → Project → Repository → Versioned Test Case → Test Plan → Test Cycle → Step-Level Execution → Interactive Dashboard

The slice includes REST APIs, RBAC, audit events, persistence, Docker deployment, and GUI quality foundations. Bulk operations, import/export, background jobs, and production hardening then complete Phase 1.

Traceability relationships and UI flows must be designed during this phase even though the complete requirement/defect matrix is delivered in Phase 2. AI generation must be architecturally anticipated but implemented only after the core lifecycle, traceability, reporting, and GUI are stable.
