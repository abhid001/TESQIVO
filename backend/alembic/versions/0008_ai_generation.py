"""ai generation + suggestions

Revision ID: 0008_ai_generation
Revises: 0007_hash_session_tokens
Create Date: 2026-11-06

Tables for the AI test-case generator (PRS §17). Inspector-guarded so it converges
whether 0001's create_all already produced the tables (fresh DB) or not.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0008_ai_generation"
down_revision = "0007_hash_session_tokens"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if not _has_table("ai_generation"):
        op.create_table(
            "ai_generation",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("requested_by", sa.Uuid(), nullable=False),
            sa.Column("job_id", sa.Uuid(), nullable=True),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="queued"),
            sa.Column("source_refs", sa.JSON(), nullable=False),
            sa.Column("story_text", sa.Text(), nullable=True),
            sa.Column("options", sa.JSON(), nullable=False),
            sa.Column("provider", sa.String(length=32), nullable=True),
            sa.Column("model", sa.String(length=80), nullable=True),
            sa.Column("prompt_version", sa.String(length=16), nullable=False),
            sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("assumptions", sa.JSON(), nullable=False),
            sa.Column("open_questions", sa.JSON(), nullable=False),
            sa.Column("error_summary", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.CheckConstraint(
                "status in ('queued','running','completed','failed')",
                name="ck_ai_generation_ai_generation_status_valid",
            ),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_ai_generation_project_id_project"),
            sa.ForeignKeyConstraint(["requested_by"], ["app_user.id"], name="fk_ai_generation_requested_by_app_user"),
            sa.ForeignKeyConstraint(["job_id"], ["background_job.id"], name="fk_ai_generation_job_id_background_job"),
            sa.PrimaryKeyConstraint("id", name="pk_ai_generation"),
        )
        op.create_index("ix_ai_generation_project_id", "ai_generation", ["project_id"])
        op.create_index("ix_ai_generation_created_at", "ai_generation", ["created_at"])

    if not _has_table("ai_suggestion"):
        op.create_table(
            "ai_suggestion",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("generation_id", sa.Uuid(), nullable=False),
            sa.Column("project_id", sa.Uuid(), nullable=False),
            sa.Column("ordinal", sa.Integer(), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
            sa.Column("edited", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("possible_duplicate_of", sa.String(length=32), nullable=True),
            sa.Column("decided_by", sa.Uuid(), nullable=True),
            sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("reject_reason", sa.String(length=500), nullable=True),
            sa.Column("test_case_id", sa.Uuid(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.CheckConstraint(
                "status in ('pending','accepted','rejected')",
                name="ck_ai_suggestion_ai_suggestion_status_valid",
            ),
            sa.UniqueConstraint("generation_id", "ordinal", name="unique_suggestion_ordinal"),
            sa.ForeignKeyConstraint(["generation_id"], ["ai_generation.id"], name="fk_ai_suggestion_generation_id_ai_generation"),
            sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_ai_suggestion_project_id_project"),
            sa.ForeignKeyConstraint(["decided_by"], ["app_user.id"], name="fk_ai_suggestion_decided_by_app_user"),
            sa.ForeignKeyConstraint(["test_case_id"], ["test_case.id"], name="fk_ai_suggestion_test_case_id_test_case"),
            sa.PrimaryKeyConstraint("id", name="pk_ai_suggestion"),
        )
        op.create_index("ix_ai_suggestion_generation_id", "ai_suggestion", ["generation_id"])
        op.create_index("ix_ai_suggestion_project_id", "ai_suggestion", ["project_id"])


def downgrade() -> None:
    if _has_table("ai_suggestion"):
        op.drop_table("ai_suggestion")
    if _has_table("ai_generation"):
        op.drop_table("ai_generation")
