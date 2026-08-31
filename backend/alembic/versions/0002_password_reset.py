"""self-service password reset: must_change_password flag

Revision ID: 0002_password_reset
Revises: 0001_initial
Create Date: 2026-08-28

Inspector-guarded: on a fresh database 0001's create_all builds every column
from the live model metadata, so ``must_change_password`` already exists; on a
database that predates the flag it does not. Either way this migration converges.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_password_reset"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    if "must_change_password" not in _cols("app_user"):
        op.add_column(
            "app_user",
            sa.Column(
                "must_change_password",
                sa.Boolean(),
                nullable=False,
                server_default=sa.false(),
            ),
        )
        op.alter_column("app_user", "must_change_password", server_default=None)


def downgrade() -> None:
    if "must_change_password" in _cols("app_user"):
        op.drop_column("app_user", "must_change_password")
