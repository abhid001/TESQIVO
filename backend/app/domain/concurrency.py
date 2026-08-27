"""Optimistic concurrency helpers (PRS §13).

Critical updates, transitions, and deletes require the caller to pass the version
they observed. A mismatch raises VERSION_CONFLICT.
"""

from __future__ import annotations

from app.core.errors import ValidationFailed, VersionConflict


def check_version(current: int, expected: int | None, *, entity: str) -> None:
    if expected is None:
        raise ValidationFailed(
            "This change requires the expected version.",
            details=[{"field": "/expected_version", "code": "REQUIRED", "message": "Required."}],
        )
    if current != expected:
        raise VersionConflict(
            f"The {entity} was modified by someone else. Reload and try again.",
        )
