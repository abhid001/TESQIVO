# Artifact 7 — Logical Component Architecture and Service Boundaries

**Question answered:** How is the codebase layered so that GUI, REST, import, bulk, and
future automation all go through one domain path? (PRS §2, §21)

```mermaid
flowchart TB
    subgraph Client
        SPA[React SPA - design system, TanStack Query]
    end

    subgraph Edge
        CADDY[Caddy - TLS, static SPA, /api proxy]
    end

    subgraph API [FastAPI process]
        MW[Middleware: correlation id, session auth, rate limit, error mapper]
        RT[Routers /api/v1/* - transport only: parse, call service, serialize]
        subgraph DOMAIN [Domain services - the ONLY write path]
            AUTHZ[Authorization service - concrete condition checks]
            TCS[test_case service + versioning + controlled fields]
            PCS[plan / cycle / cycle_test service + snapshot]
            EXE[execution service + result derivation + authoritative attempt]
            TRC[traceability service - link rules + impact paths]
            RPT[reporting service - M-01..M-13, one query layer]
            REQD[requirement / release / defect service]
            BULK[bulk service - preview / confirm / captured scope]
            IMP[import service - map / validate / strict|partial]
            ATT[attachment service - allowlist, safe names, authz]
            AUD[audit service - append in same tx]
            IDS[identity / key minting service]
        end
        subgraph PORTS [Outbound ports - stable interfaces]
            BLOB[BlobStore]
            QUEUE[JobQueue]
            CLK[Clock]
            SYNC[ExternalSyncPort - Phase 2, no impl]
            INGEST[AutomationIngestPort - Phase 2, no impl]
            AIGEN[AiGenerationPort - Phase 3, no impl]
        end
        REPO[Repositories - SQLAlchemy, per aggregate]
    end

    subgraph Worker [RQ worker process]
        WJOBS[Job handlers: bulk apply, CSV import, large export, orphan cleanup]
    end

    PG[(PostgreSQL)]
    RD[(Redis)]
    VOL[(Attachment volume)]

    SPA --> CADDY --> MW --> RT --> DOMAIN
    DOMAIN --> REPO --> PG
    DOMAIN --> AUD --> REPO
    DOMAIN --> PORTS
    BLOB --> VOL
    QUEUE --> RD
    RT -->|202 + Job| QUEUE
    Worker --> RD
    WJOBS --> DOMAIN
    WJOBS --> PG
```

## Layer rules

| Layer | May depend on | Must not |
|---|---|---|
| Routers | domain services, schemas | touch repositories or the ORM session directly for writes |
| Domain services | repositories, ports, other domain services, audit | know about HTTP, FastAPI, request objects |
| Repositories | ORM models, session | contain business rules / authorization |
| Ports | stdlib / typing only | import domain or infra |
| Worker handlers | domain services | re-implement domain rules |

## Request lifecycle (write)

1. Middleware attaches `correlation_id`, resolves session → `actor` (User + memberships).
2. Router validates the Pydantic request body, extracts `If-Match`/`Idempotency-Key`.
3. Router calls exactly one domain service function with `actor`, DTO, concurrency token.
4. Domain service: authorize → validate invariants → begin tx → mutate via repo →
   write audit event → commit → return domain result.
5. Error mapper converts `DomainError` subclasses to the PRS §13 error envelope.

## Transaction boundaries

- Single mutation + its audit event + key minting = one transaction.
- Cycle activation = one transaction (snapshot all cycle tests + audit) — atomic.
- Bulk "ordinary" = one transaction **per item** (partial success allowed).
- Strict CSV import = one transaction for the whole valid batch (all-or-nothing).
