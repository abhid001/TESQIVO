"""scenarios: Requirement -> Scenario -> Test Case

Revision ID: 0003_scenarios
Revises: 0002_password_reset
Create Date: 2026-08-28

Inspector-guarded: on a fresh database 0001's create_all already builds the
``scenario`` table and the ``test_case.scenario_id`` link from the live model
metadata; on an older database it does not. Either way this migration converges.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0003_scenarios"
down_revision = "0002_password_reset"
branch_labels = None
depends_on = None


def _insp():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return _insp().has_table(name)


def _cols(table: str) -> set[str]:
    return {c["name"] for c in _insp().get_columns(table)}


def _indexes(table: str) -> set[str]:
    return {i["name"] for i in _insp().get_indexes(table)}


def _fks(table: str) -> set[str]:
    return {fk["name"] for fk in _insp().get_foreign_keys(table)}


def upgrade() -> None:
    if not _has_table("scenario"):
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

    scenario_indexes = _indexes("scenario")
    if "ix_scenario_project_id" not in scenario_indexes:
        op.create_index("ix_scenario_project_id", "scenario", ["project_id"])
    if "ix_scenario_requirement_id" not in scenario_indexes:
        op.create_index("ix_scenario_requirement_id", "scenario", ["requirement_id"])

    if "scenario_id" not in _cols("test_case"):
        op.add_column("test_case", sa.Column("scenario_id", sa.Uuid(), nullable=True))
    if "fk_test_case_scenario_id_scenario" not in _fks("test_case"):
        op.create_foreign_key(
            "fk_test_case_scenario_id_scenario", "test_case", "scenario", ["scenario_id"], ["id"]
        )
    if "ix_test_case_scenario_id" not in _indexes("test_case"):
        op.create_index("ix_test_case_scenario_id", "test_case", ["scenario_id"])


def downgrade() -> None:
    if "ix_test_case_scenario_id" in _indexes("test_case"):
        op.drop_index("ix_test_case_scenario_id", "test_case")
    if "fk_test_case_scenario_id_scenario" in _fks("test_case"):
        op.drop_constraint("fk_test_case_scenario_id_scenario", "test_case", type_="foreignkey")
    if "scenario_id" in _cols("test_case"):
        op.drop_column("test_case", "scenario_id")
    if _has_table("scenario"):
        op.drop_table("scenario")
