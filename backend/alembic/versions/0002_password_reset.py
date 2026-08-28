"""self-service password reset: must_change_password flag

Revision ID: 0002_password_reset
Revises: 0001_initial
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002_password_reset"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
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
    op.drop_column("app_user", "must_change_password")
