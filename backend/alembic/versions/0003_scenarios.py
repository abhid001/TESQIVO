"""scenarios: Requirement -> Scenario -> Test Case

Revision ID: 0003_scenarios
Revises: 0002_password_reset
Create Date: 2026-08-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_scenarios"
down_revision = "0002_password_reset"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scenario",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("key", sa.String(length=32), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('active','archived')", name="ck_scenario_scenario_status_valid"),
        sa.ForeignKeyConstraint(["project_id"], ["project.id"], name="fk_scenario_project_id_project"),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirement.id"], name="fk_scenario_requirement_id_requirement"),
        sa.ForeignKeyConstraint(["owner_id"], ["app_user.id"], name="fk_scenario_owner_id_app_user"),
        sa.ForeignKeyConstraint(["created_by"], ["app_user.id"], name="fk_scenario_created_by_app_user"),
        sa.PrimaryKeyConstraint("id", name="pk_scenario"),
        sa.UniqueConstraint("key", name="uq_scenario_key"),
    )
    op.create_index("ix_scenario_project_id", "scenario", ["project_id"])
    op.create_index("ix_scenario_requirement_id", "scenario", ["requirement_id"])

    op.add_column("test_case", sa.Column("scenario_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_test_case_scenario_id_scenario", "test_case", "scenario", ["scenario_id"], ["id"]
    )
    op.create_index("ix_test_case_scenario_id", "test_case", ["scenario_id"])


def downgrade() -> None:
    op.drop_index("ix_test_case_scenario_id", "test_case")
    op.drop_constraint("fk_test_case_scenario_id_scenario", "test_case", type_="foreignkey")
    op.drop_column("test_case", "scenario_id")
    op.drop_index("ix_scenario_requirement_id", "scenario")
    op.drop_index("ix_scenario_project_id", "scenario")
    op.drop_table("scenario")
