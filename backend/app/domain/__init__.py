"""Domain services - the single write path for GUI, REST, import, bulk, automation.

Rules (PRS §21):
- Every write operation authorizes against concrete conditions before mutating.
- Audit events are written in the same transaction as the mutation.
- Immutable records are never rewritten; corrections are append-only.
- Optimistic concurrency is enforced on mutable aggregate roots.
"""
