# Artifact 4 — Plan, Cycle, Cycle Test, and Execution Attempt State Diagrams

**Question answered:** What are the lifecycle states and guarded transitions for the
execution side of the domain, and where does snapshotting happen? (PRS §7)

## Test Plan

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Draft
    Draft --> Active : activate (>=1 cycle OR >=1 scoped test)
    Active --> Completed : complete
    Completed --> Active : reopen (authorized manager + reason)
    Draft --> Archived
    Active --> Archived
    Completed --> Archived
```

## Test Cycle

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Draft
    Draft --> Active : activate (>=1 Cycle Test)\n[SNAPSHOT approved version -> each Cycle Test]
    Active --> Completed : complete (no IN_PROGRESS attempt)
    Completed --> Reopened : reopen (authorized manager + reason)
    Reopened --> Completed : complete
    Draft --> Archived
    Active --> Archived
    Completed --> Archived
    Reopened --> Archived

    note right of Active
        Draft: scope changes free.
        Active/Reopened: scope add/remove audited.
        NOT_RUN cycle test may be refreshed to a
        newer approved version by a manager.
        A cycle test with IN_PROGRESS/completed
        attempt cannot be silently refreshed.
    end note
```

## Cycle Test (displayed result is derived, not stored as truth)

```mermaid
stateDiagram-v2
    direction LR
    [*] --> NOT_RUN
    NOT_RUN --> IN_PROGRESS : start attempt
    IN_PROGRESS --> PASSED : attempt completed PASSED
    IN_PROGRESS --> FAILED : attempt completed FAILED
    IN_PROGRESS --> BLOCKED : attempt completed BLOCKED
    IN_PROGRESS --> SKIPPED : attempt completed SKIPPED
    IN_PROGRESS --> ABORTED : attempt aborted
    PASSED --> RETEST_PENDING : retest requested
    FAILED --> RETEST_PENDING : retest requested
    BLOCKED --> RETEST_PENDING : retest requested
    SKIPPED --> RETEST_PENDING : retest requested
    ABORTED --> RETEST_PENDING : retest requested
    RETEST_PENDING --> IN_PROGRESS : new attempt started
```

The displayed value = result of the **authoritative attempt** (PRS §7.5), or `NOT_RUN`
if none, or `RETEST_PENDING` when a retest was requested and the new attempt is not
complete. It is computed on read, never written as the source of truth.

## Execution Attempt (immutable once terminal)

```mermaid
stateDiagram-v2
    direction LR
    [*] --> IN_PROGRESS : POST /cycle-tests/{id}/attempts
    IN_PROGRESS --> PASSED
    IN_PROGRESS --> FAILED
    IN_PROGRESS --> BLOCKED
    IN_PROGRESS --> SKIPPED
    IN_PROGRESS --> ABORTED : abort (reason)
    PASSED --> [*]
    FAILED --> [*]
    BLOCKED --> [*]
    SKIPPED --> [*]
    ABORTED --> [*]

    note right of PASSED
        Terminal attempts are content-immutable.
        A manager correction = new execution_correction
        row {old, new, actor, reason, time}; the original
        attempt evidence is never rewritten.
    end note
```

## Overall-result derivation (PRS §7.4) — pure function

```mermaid
flowchart TD
    A[All required steps have a result?] -->|no| IP[IN_PROGRESS]
    A -->|yes| B{Any required step FAILED?}
    B -->|yes| F[FAILED]
    B -->|no| C{Any required step BLOCKED?}
    C -->|yes| BL[BLOCKED]
    C -->|no| D{All required steps PASSED or SKIPPED?}
    D -->|yes| P[PASSED]
    D -->|no| IP
```

`SKIPPED` and `ABORTED` are terminal but non-passing. An override of the derived result
requires permission + audited reason.
