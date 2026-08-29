"""feedback + project access requests

Revision ID: 0004_feedback_access
Revises: 0003_scenarios
Create Date: 2026-08-29

Guarded with an inspector: on a fresh database 0001 creates every table from the
live model metadata, so these may already exist; on an existing database they do
not. Either way this migration converges.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004_feedback_access"
down_revision = "0003_scenarios"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("project_access_request"):
        op.create_table(
            "project_access_request",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("requested_role", sa.String(length=20), nullable=False, server_default="tester"),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("decided_by", sa.Uuid(), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "status in ('pending','approved','denied')",
                name="ck_project_access_request_access_request_status_valid",
            ),
            sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name="fk_project_access_request_user_id_app_user"),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_project_access_request_project_id_project"),
            sa.ForeignKeyConstraint(["decided_by"], ["app_user.id"], name="fk_project_access_request_decided_by_app_user"),
            sa.PrimaryKeyConstraint("id", name="pk_project_access_request"),
        )
        op.create_index("ix_project_access_request_user_id", "project_access_request", ["user_id"])
        op.create_index("ix_project_access_request_project_id", "project_access_request", ["project_id"])

    if not _has_table("feedback"):
        op.create_table(
            "feedback",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=True),
            sa.Column("category", sa.String(length=16), nullable=False, server_default="other"),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("page_path", sa.String(length=400), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="open"),
            sa.Column("admin_note", sa.Text(), nullable=True),
            sa.Column("resolved_by", sa.Uuid(), nullable=True),
            sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "category in ('bug','idea','question','other')",
                name="ck_feedback_feedback_category_valid",
            ),
            sa.CheckConstraint(
                "status in ('open','reviewing','resolved')",
                name="ck_feedback_feedback_status_valid",
            ),
            sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], name="fk_feedback_user_id_app_user"),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_feedback_project_id_project"),
            sa.ForeignKeyConstraint(["resolved_by"], ["app_user.id"], name="fk_feedback_resolved_by_app_user"),
            sa.PrimaryKeyConstraint("id", name="pk_feedback"),
        )
        op.create_index("ix_feedback_user_id", "feedback", ["user_id"])
        op.create_index("ix_feedback_project_id", "feedback", ["project_id"])


def downgrade() -> None:
    if _has_table("feedback"):
        op.drop_table("feedback")
    if _has_table("project_access_request"):
        op.drop_table("project_access_request")
