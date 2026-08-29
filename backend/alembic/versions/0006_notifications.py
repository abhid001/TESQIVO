"""notifications

Revision ID: 0006_notifications
Revises: 0005_requirement_fields
Create Date: 2026-08-29

Inspector-guarded so it converges whether 0001's create_all already produced
the table (fresh DB) or not (existing DB).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0006_notifications"
down_revision = "0005_requirement_fields"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("notification"):
        return
    op.create_table(
        "notification",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.String(length=500), nullable=True),
        sa.Column("link", sa.String(length=200), nullable=True),
        sa.Column("ref_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name="fk_notification_user_id_app_user"),
        sa.PrimaryKeyConstraint("id", name="pk_notification"),
    )
    op.create_index("ix_notification_user_id", "notification", ["user_id"])
    op.create_index("ix_notification_created_at", "notification", ["created_at"])


def downgrade() -> None:
    if _has_table("notification"):
        op.drop_table("notification")
