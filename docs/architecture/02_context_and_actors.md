# Artifact 1 — Product Context and Actors

**Question answered:** Who uses TESQIVO, what external systems does it touch in Phase 1,
and which touchpoints are deferred?

```mermaid
flowchart TB
    subgraph Actors
        SA[System Administrator]
        PA[Project Administrator]
        TM[Test Manager / QA Lead]
        MT[Manual Tester]
        AE[Automation Engineer]
        DEV[Developer]
        RM[Release Manager]
        AUD[Auditor / Read-only Stakeholder]
    end

    subgraph TESQIVO [TESQIVO Phase 1 - self-hosted]
        UI[Web UI]
        API[REST API /api/v1]
        WRK[Background Worker]
        DB[(PostgreSQL)]
        BLOB[(Attachment Volume)]
    end

    SA --> UI
    PA --> UI
    TM --> UI
    MT --> UI
    RM --> UI
    AUD --> UI
    AE -->|scripts / curl| API
    DEV -->|scripts / curl| API

    UI --> API
    API --> DB
    API --> WRK
    WRK --> DB
    API --> BLOB
    WRK --> BLOB

    subgraph Deferred [Deferred - interface only]
        CICD[CI/CD systems - Phase 2]
        ALM[Jira / GitLab / GitHub / Azure DevOps - Phase 2]
        S3[S3-compatible storage - Phase 2]
        LLM[AI provider - Phase 3]
        IDP[Enterprise SSO / IdP - Phase 4]
    end

    API -.->|AutomationIngestPort| CICD
    API -.->|ExternalSyncPort| ALM
    BLOB -.->|BlobStore impl| S3
    WRK -.->|AiGenerationPort| LLM
    API -.->|AuthN provider| IDP
```

**Phase 1 boundary notes**

- The only inbound integration surface in Phase 1 is the documented REST API used by
  humans and ad-hoc automation scripts. No webhooks, no API tokens (session auth only),
  no inbound ALM sync.
- Email is **not** in Phase 1 scope. Password reset issues a one-time token surfaced to
  a System Admin / printed to the API response for an admin-initiated reset
  (decision D-004).
- All deferred connectors are represented in code as ports with a single Phase 1
  in-process implementation (local blob store) or no implementation (raise
  `NotImplementedError` guarded by feature flag defaulting off).
