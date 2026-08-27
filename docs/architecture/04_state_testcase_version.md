# Artifact 3 — Test Case / Test Case Version Lifecycle and Versioning

**Question answered:** How do the logical Test Case state and the per-version review
state interact, and exactly when is a new version forked? (PRS §6)

## Two coupled state machines

The **logical Test Case** has a lifecycle state. Each **Test Case Version** has a review
status. The logical state is *derived* from versions + lifecycle events.

```mermaid
stateDiagram-v2
    direction LR
    [*] --> Draft : create test case (auto v1 Draft)

    Draft --> InReview : submit for review (title + >=1 valid step)
    InReview --> Draft : request changes
    InReview --> Approved : approve (applies to this version)
    Approved --> Active : activate (sets approved_version_id as selectable)
    Active --> Deprecated : deprecate (excluded from new selection)
    Deprecated --> Active : reinstate
    Active --> Archived : archive
    Deprecated --> Archived : archive
    Approved --> Archived : archive
    Draft --> Archived : archive
    Archived --> Draft : restore (policy: re-review) 
    Archived --> Active : restore (policy: prior state)

    note right of Approved
        Controlled-field edit on Approved/Active
        forks a NEW Draft version.
        Previous approved/active version stays
        available to existing cycles & executions.
    end note
```

## Version fork decision

```mermaid
flowchart TD
    Edit[Edit request on a Test Case] --> Q{Field in controlled set?}
    Q -->|title, description, preconditions,\nstep.action, step.expected, step.order,\nstep.required, controlled metadata| Fork
    Q -->|folder, tags, assignment,\nnon-controlled metadata| NoFork

    Fork --> Q2{Current version status}
    Q2 -->|Draft| Mutate[Mutate current Draft in place]
    Q2 -->|In Review / Approved / Active| NewDraft[Create new Draft version N+1\ncopy content, apply change,\nset current_version_id = N+1]
    NoFork --> AuditOnly[Update logical Test Case row\nwrite audit event\nno version change]

    Mutate --> Audit[Write audit event]
    NewDraft --> Audit
```

**Controlled-field list** is a single constant in `domain/test_case/controlled_fields.py`
(PRS §6.2 "centralized in the domain service"). Changing it is a code+migration change,
never per-project config in Phase 1.

## Invariants

- `current_version_id` always points to the newest version (max `version_number`).
- `approved_version_id` is null until first approval; points at the version approved,
  not necessarily the newest.
- A version row, once its status leaves `Draft`, is content-immutable. Enforced by a
  DB trigger + domain guard.
- Draft → In Review requires: non-empty title AND ≥1 step with non-empty action and
  expected result.
- Invalid transition → `409 STATE_TRANSITION_NOT_ALLOWED`.
- Archive never cascades to cycles, executions, links, attachments, audit (PRS §6.3).
