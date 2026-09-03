"""project membership: partial unique index on active rows only

Revision ID: 0008_membership_partial_unique
Revises: 0007_hash_session_tokens
Create Date: 2026-09-03

The old UNIQUE(project_id, user_id, status) let a user be removed once but broke
on the second removal (two status='removed' rows). Replace it with a partial
unique index that only constrains status='active' (finding #4).

Inspector-guarded: on a fresh DB 0001's create_all already builds the new index
from the model and never builds the old constraint.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_membership_partial_unique"
down_revision = "0007_hash_session_tokens"
branch_labels = None
depends_on = None

_TABLE = "project_membership"
_OLD = "one_active_membership"
_NEW = "uq_project_membership_active"


def _insp():
    return sa.inspect(op.get_bind())


def _constraints() -> set[str]:
    i = _insp()
    return {c["name"] for c in i.get_unique_constraints(_TABLE)}


def _indexes() -> set[str]:
    return {i["name"] for i in _insp().get_indexes(_TABLE)}


def upgrade() -> None:
    if not _insp().has_table(_TABLE):
        return
    if _OLD in _constraints():
        op.drop_constraint(_OLD, _TABLE, type_="unique")
    if _NEW not in _indexes():
        op.create_index(
            _NEW, _TABLE, ["project_id", "user_id"],
            unique=True, postgresql_where=sa.text("status = 'active'"),
            sqlite_where=sa.text("status = 'active'"),
        )


def downgrade() -> None:
    if not _insp().has_table(_TABLE):
        return
    if _NEW in _indexes():
        op.drop_index(_NEW, table_name=_TABLE)
    if _OLD not in _constraints():
        op.create_unique_constraint(_OLD, _TABLE, ["project_id", "user_id", "status"])
