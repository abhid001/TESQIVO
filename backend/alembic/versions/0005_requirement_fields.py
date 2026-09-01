"""requirement: acceptance_criteria + labels

Revision ID: 0005_requirement_fields
Revises: 0004_feedback_access
Create Date: 2026-08-29

Column adds are guarded with an inspector so they converge whether 0001's
create_all already produced them (fresh DB) or not (existing DB).
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0005_requirement_fields"
down_revision = "0004_feedback_access"
branch_labels = None
depends_on = None


def _cols(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    have = _cols("requirement")
    if "acceptance_criteria" not in have:
        op.add_column("requirement", sa.Column("acceptance_criteria", sa.Text(), nullable=True))
    if "labels" not in have:
        op.add_column("requirement", sa.Column("labels", sa.String(length=400), nullable=True))


def downgrade() -> None:
    have = _cols("requirement")
    if "labels" in have:
        op.drop_column("requirement", "labels")
    if "acceptance_criteria" in have:
        op.drop_column("requirement", "acceptance_criteria")
