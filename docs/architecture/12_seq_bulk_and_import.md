# Artifact 11 — Bulk-Job and CSV Import Sequences

**Question answered:** Where are the transaction boundaries, how is scope captured, and
how do retries avoid duplicate success? (PRS §11, §12)

## Bulk operation (preview → confirm → run)

```mermaid
sequenceDiagram
    actor M as Test Manager
    participant API
    participant BULK as bulk service
    participant Q as JobQueue (Redis)
    participant W as Worker
    participant DB
    M->>API: POST /bulk/preview {action, ids? XOR filter?}
    Note over BULK: exactly one of ids/filter; never both
    API->>BULK: preview(actor, req)
    BULK->>DB: resolve scope (read only), per-item authz + validation dry run
    BULK-->>API: {resolved_count, sample, authz_failures, warnings, impact} (NO mutation)

    M->>API: POST /bulk/confirm {preview_token, Idempotency-Key}
    API->>BULK: confirm(...)
    alt idempotency key seen with same payload
        BULK-->>API: 200 original job (no new job)
    else
        BULK->>DB: INSERT background_job {status=queued, scope_snapshot = resolved ids or captured filter@now}
        BULK->>DB: INSERT job_item rows (mutation_key per item)
        BULK->>Q: enqueue job id
        BULK-->>API: 202 + Job resource
    end

    W->>Q: pick job
    W->>DB: acquire lease (lease_owner, lease_expires_at) via conditional UPDATE
    loop each pending job_item
        W->>DB: BEGIN (one tx per item)
        W->>W: re-evaluate authz + domain validation for this item NOW
        alt fails
            W->>DB: job_item.status=failed/skipped + error_code; COMMIT
        else
            W->>W: call the SAME domain service a single action uses
            W->>DB: mutation + audit_event(job_id); job_item.status=succeeded (keyed by mutation_key); COMMIT
        end
        W->>DB: renew lease
    end
    W->>DB: job.status = completed | partially_completed | failed; counts
```

- **Filter captured at confirm time**: rows created later never enter the job.
- **Cancellation** is best-effort (flag checked between items); committed items are not
  rolled back.
- **Retry / worker restart**: `job_item.mutation_key` unique per `(job_id, key)` — a
  re-run of an already-succeeded item is a no-op, not a second mutation.
- Lease expiry lets another worker resume a job whose worker died.

## CSV import (Upload → Map → Preview → Validate → strict|partial → Confirm)

```mermaid
sequenceDiagram
    actor M
    participant API
    participant IMP as import service
    participant W as Worker
    participant DB
    M->>API: POST /imports {entity_type, file}
    API->>IMP: stage file -> parse headers
    IMP-->>API: {import_id, detected_columns}
    M->>API: PUT /imports/{id}/mapping {column -> field, duplicate_policy, stable_id_field}
    M->>API: POST /imports/{id}/validate
    API->>IMP: validate every row (types, refs, authz, domain rules)
    IMP-->>API: {valid_rows, invalid_rows, error_file_ref}
    M->>API: POST /imports/{id}/confirm {mode: strict|partial, Idempotency-Key}
    API->>DB: INSERT background_job(type=import)
    API-->>API: 202 + Job
    W->>DB: process
    alt mode = strict
        W->>DB: BEGIN one tx for the WHOLE valid batch
        W->>W: apply each row via domain service (create/update by stable id)
        alt any row errors
            W->>DB: ROLLBACK -> commits nothing; job failed; full error file
        else
            W->>DB: COMMIT; job completed
        end
    else mode = partial
        loop each valid row
            W->>DB: BEGIN per-row; apply; COMMIT or record item error
        end
        W->>DB: job partially_completed if any failures; downloadable error file
    end
```

Import uses normal authorization, versioning (creates Draft versions where controlled
fields change), domain services, and audit — no bypass path.

## Large export as a job

`GET .../export.csv` small + synchronous; over a row threshold → `202` + Job → worker
writes CSV to blob → time-limited signed download URL (authorized scope captured).
