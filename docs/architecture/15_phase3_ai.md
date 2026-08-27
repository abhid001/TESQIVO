# Artifact 14 — Phase 3 AI Generation / Review / Approval Flow (Anticipated)

**Question answered:** What boundary must Phase 1 preserve so AI test generation can be
added later without letting AI output bypass review, versioning, coverage, or audit?
(PRS §17)

> **Deferred.** Phase 1 ships the `AiGenerationPort` interface with **no
> implementation**, no provider config, no routes, feature flag `AI_GENERATION=off`.

```mermaid
flowchart TD
    SRC[Authorized source selection\nrequirements / stories / acceptance criteria / docs] --> GJ[Generation Job - async]
    GJ --> PA[Provider adapter - behind AiGenerationPort]
    PA --> VAL[Structured-output validation\nagainst suggestion schema]
    VAL --> RW[Review workspace]
    RW --> DUP[Duplicate + policy checks]
    DUP --> DEC{Reviewer decision}
    DEC -->|reject| LOG[audit + generation_result retains rejection]
    DEC -->|accept| DR[Accepted item -> Draft Test Case\nvia normal test_case domain service]
    DR --> NR[Normal review / approval / activation]
    NR --> COV[Only then counts as coverage]

    subgraph Guards
        G1[Reads only sources the requesting user can access]
        G2[Sends content to provider only if instance privacy policy permits]
        G3[Prompt-injection handling on source documents]
        G4[Provider timeout / retry / rate / cost controls]
        G5[AI Drafts never count as coverage - M-05/M-06/M-08 exclude them]
        G6[Provider cannot write to the repository directly]
    end
```

## What Phase 1 must already guarantee

| Requirement on Phase 1 | Where honored |
|---|---|
| A Test Case can only become coverage-qualifying via approve+activate | version state machine (Artifact 3); M-05/06/08 predicates check `approved`/`active` only |
| `test_case_version.source_type` can record `ai_generated` | enum has room; Phase 1 uses `manual`/`import` |
| Creating a Draft test is a pure domain-service call (no GUI coupling) | `test_case_service.create()` takes a DTO |
| Audit records actor + source for every creation | `audit_event.source` enum extensible; `actor_type` includes `system` |
| Async job infra with per-item results, retention, cancellation | `background_job` / `job_item` generic |
| Attachment / document access is authz-checked per parent | attachment service |

## Explicitly out of Phase 1

Provider adapters, prompt templates + versioning, `generation_job` / `suggestion` /
`generation_result` tables, review workspace UI, duplicate-detection model, evaluation
datasets, quality thresholds, coverage-gap analytics, flaky/effectiveness/risk models.
