"""Shared sorting helpers (PRS §13: ``sort=field,-other_field``).

Default ordering across the app is alphanumeric / natural: readable keys of the
form ``PROJ-TYPE-<seq>`` are ordered by ``(length(key), key)`` so ``PROJ-TC-2``
comes before ``PROJ-TC-10`` on every backend.
"""

from __future__ import annotations

from sqlalchemy import func
from sqlalchemy.sql import ColumnElement

from app.core.errors import ValidationFailed


def natural_key_order(model) -> list[ColumnElement]:
    return [func.length(model.key), model.key]


def apply_sort(
    stmt,
    *,
    sort: str | None,
    allowed: dict[str, ColumnElement | list[ColumnElement]],
    default: list[ColumnElement],
):
    """Parse a ``sort`` query string and apply ORDER BY.

    ``allowed`` maps a public field name to the column(s) to order by. A ``-``
    prefix means descending. Unknown fields raise ``VALIDATION_ERROR``.
    """
    if not sort:
        return stmt.order_by(*default)
    clauses: list[ColumnElement] = []
    for raw in sort.split(","):
        token = raw.strip()
        if not token:
            continue
        desc = token.startswith("-")
        field = token[1:] if desc else token
        col = allowed.get(field)
        if col is None:
            raise ValidationFailed(
                f"Cannot sort by '{field}'.",
                details=[{"field": "/sort", "code": "INVALID_SORT_FIELD", "message": field}],
            )
        cols = col if isinstance(col, list) else [col]
        clauses.extend(c.desc() if desc else c.asc() for c in cols)
    if not clauses:
        return stmt.order_by(*default)
    return stmt.order_by(*clauses)
