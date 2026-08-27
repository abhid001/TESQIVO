# Artifact 5 — Traceability Relationship Model and Matrix Interaction

**Question answered:** What links are legal in Phase 1, how does a Requirement→Test Case
link resolve to a version in the matrix, and how does defect impact propagate? (PRS §8.2)

## Legal Phase 1 relationships

```mermaid
flowchart LR
    REQ[Requirement] -->|covers| TC[Test Case - logical]
    REQ -->|targets| REL[Release]
    REL -->|scopes| PLAN[Test Plan]
    REL -->|scopes| CYC[Test Cycle]
    TCV[Test Case Version] -->|planned as| CT[Cycle Test]
    CT -->|executed by| ATT[Execution Attempt]
    ATT -->|raised| DEF[Defect]
    DEF -->|regresses| REQ
    DEF -->|affects| REL
```

Any other `source_type → target_type` pair is rejected (`422 VALIDATION_ERROR`,
`code: RELATIONSHIP_NOT_ALLOWED`). All endpoints of a link must share `project_id`.

## Trace link record (first-class, soft-removable)

```
id, project_id, source_type, source_id, target_type, target_id,
relationship_type, origin (manual|import|system),
created_by, created_at, removed_by, removed_at, external_reference?
```

- Duplicate **active** (source,target,relationship) → `409 DUPLICATE_RESOURCE`.
- Removal sets `removed_*`; row is retained, excluded from normal metrics, still shown
  in data-quality views.
- Invalid / unresolved / stale / deprecated / archived links stay visible in the
  Data Quality panel (PRS §8.2, M-13).

## Matrix version resolution

```mermaid
flowchart TD
    Link[Requirement -> Test Case link - logical] --> Ctx{Matrix column scope}
    Ctx -->|a Cycle is selected| Resolve[Resolve to the Test Case Version\nthat the relevant Cycle Test snapshotted]
    Ctx -->|no cycle, design view| Design[Resolve to current/approved version]
    Resolve --> Show[Cell shows: linked logical test +\nplanned/executed version + latest authoritative result]
    Design --> Show2[Cell shows: linked logical test +\ndesign-coverage qualification only]

    Note1[A new version does NOT invalidate the link.\nMatrix distinguishes linked-logical vs version-executed.]
```

## Defect impact paths (PRS §8.2) — only these are counted

```mermaid
flowchart LR
    subgraph P1 [Direct]
        R1[Requirement] --> D1[Defect]
    end
    subgraph P2 [Execution-mediated]
        R2[Requirement] --> TC2[Test Case] --> CT2[Cycle Test] --> AT2[Execution Attempt] --> D2[Defect]
    end
    subgraph P3 [Release-mediated]
        R3[Requirement] --> RL3[Release] --> D3[Defect]
    end
```

Execution-mediated impact is valid **only** when the attempt's Cycle Test resolves to a
Test Case that is linked to the Requirement. Drill-down names the exact path used.

## Matrix interaction flow

```mermaid
sequenceDiagram
    actor U as User
    participant UI as Matrix UI
    participant RPT as Reporting Service
    participant DB as PostgreSQL
    U->>UI: open Traceability, pick scope (project, release, plan/cycle, filters)
    UI->>RPT: GET /projects/{id}/traceability/matrix?release=&cycle=&...
    RPT->>DB: one parameterised query set (links + versions + authoritative attempts)
    DB-->>RPT: rows
    RPT-->>UI: cells + {scope, filters, data_as_of, formula_version}
    U->>UI: click a cell / a metric number
    UI->>RPT: GET .../drill-down?cell=req:REL-1,scope=...
    RPT-->>UI: exact contributing records (links, versions, attempts, defects)
    U->>UI: Export CSV (same captured scope + formula_version)
    UI->>RPT: GET .../matrix.csv?<captured scope>
```
