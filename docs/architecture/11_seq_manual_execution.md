# Artifact 10 — Manual Execution Sequence (Snapshot + Correction)

**Question answered:** How does execution preserve the exact version/steps used, and how
does a post-completion correction stay non-destructive? (PRS §7.3, §7.4, §7.5)

## Cycle activation snapshot

```mermaid
sequenceDiagram
    actor M as Test Manager
    participant API
    participant CYC as cycle service
    participant DB
    M->>API: POST /cycles/{id}/transitions {to: "active", expected_version}
    API->>CYC: activate(actor, cycle_id, expected_version)
    CYC->>DB: load cycle + cycle_tests (must have >=1)
    loop each cycle_test
        CYC->>DB: read test_case.approved_version_id (+ its steps)
        alt no approved version
            CYC-->>API: 422 VALIDATION_ERROR (missing_approved_version, list keys)
        else
            CYC->>DB: set cycle_test.test_case_version_id = approved_version_id
            CYC->>DB: INSERT cycle_test_step rows = copy of approved version steps
            CYC->>DB: set cycle_test.snapshot_taken_at = now
        end
    end
    CYC->>DB: cycle.status = active; version += 1; audit_event(before/after)
    CYC-->>API: 200 cycle
```

Later edit / move / deprecate / archive of the source Test Case never touches
`cycle_test_step`. A NOT_RUN cycle test may be explicitly refreshed:
`POST /cycle-tests/{id}/refresh-version` (manager, cycle test has no attempt).

## Run an attempt

```mermaid
sequenceDiagram
    actor T as Tester
    participant API
    participant EXE as execution service
    participant DB
    T->>API: POST /cycle-tests/{id}/attempts
    API->>EXE: start_attempt(actor, cycle_test_id)
    EXE->>EXE: authorize (assigned_to == actor OR manager)
    EXE->>DB: guard: no other IN_PROGRESS attempt for this cycle_test
    EXE->>DB: INSERT execution_attempt (status=IN_PROGRESS, copy env/build/release/version from cycle_test + cycle)
    EXE->>DB: INSERT execution_step rows = NOT_RUN per cycle_test_step
    EXE-->>API: 201 attempt (Location)
    loop each step
        T->>API: PATCH /attempts/{id}/steps/{ordinal} {result, comment}
        API->>EXE: set_step_result(...)  (attempt must be IN_PROGRESS)
        EXE->>DB: update execution_step; recorded_at = now
    end
    T->>API: POST /attempts/{id}/complete {override?, override_reason?}
    API->>EXE: complete_attempt(...)
    EXE->>EXE: derive overall_result (pure fn, PRS §7.4)
    alt override present
        EXE->>EXE: authorize(attempt.override); require reason
    end
    EXE->>DB: attempt.status/overall_result/ended_at/duration; audit_event
    EXE-->>API: 200 attempt (terminal, now immutable)
```

## Retest and correction

```mermaid
sequenceDiagram
    actor M as Test Manager
    participant API
    participant EXE
    participant DB
    Note over API: RETEST
    M->>API: POST /cycle-tests/{id}/retest
    API->>EXE: request_retest(...) -> cycle_test displayed = RETEST_PENDING
    M->>API: POST /cycle-tests/{id}/attempts  (new attempt, earlier attempts untouched)

    Note over API: CORRECTION of a completed attempt
    M->>API: POST /attempts/{id}/corrections {field:"overall_result", new_value:"PASSED", reason}
    API->>EXE: correct_attempt(...)
    EXE->>EXE: authorize(attempt.correct); attempt must be terminal
    EXE->>DB: INSERT execution_correction {old, new, actor, reason, created_at}
    EXE->>DB: audit_event; DO NOT modify execution_attempt / execution_step rows
    EXE-->>API: 200 {attempt, corrections:[...]}
```

## Authoritative attempt resolution (read side — PRS §7.5)

```mermaid
flowchart TD
    Scope[Reporting scope: project, cycle, env, build, release, filters] --> Q[all completed attempts in scope for the cycle_test]
    Q --> S[sort key:\n1. latest execution_correction.created_at if any\n2. attempt.ended_at\n3. attempt.id  (deterministic tie-break)]
    S --> Pick[authoritative = last]
    Pick --> Effective[effective result = latest correction.new_value for overall_result,\nelse attempt.overall_result]
    IP[any IN_PROGRESS attempt] --> ShownSeparately[shown separately, does not replace latest completed]
```
