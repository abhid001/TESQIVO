"""initial schema + metric definitions

Revision ID: 0001_initial
Revises:
Create Date: 2026-08-27

Greenfield v1: the schema is created from the SQLAlchemy model metadata, which is
the single source of truth. Subsequent migrations are ordinary incremental scripts.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.core.db import Base
from app import models  # noqa: F401

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None

_METRICS = [
    ("M-01", "Scoped tests"),
    ("M-02", "Execution completion"),
    ("M-03", "Pass rate"),
    ("M-04", "Not-run count"),
    ("M-05", "Design coverage"),
    ("M-06", "Plan coverage"),
    ("M-07", "Execution coverage"),
    ("M-08", "Pass coverage"),
    ("M-09", "Requirements uncovered"),
    ("M-10", "Open critical defects"),
    ("M-11", "Defect-affected requirements"),
    ("M-12", "Automation coverage"),
    ("M-13", "Trace-link completeness"),
]


def upgrade() -> None:
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)
    md = sa.Table("metric_definition", sa.MetaData(), autoload_with=bind)
    op.bulk_insert(
        md,
        [
            {
                "metric_id": mid,
                "formula_version": 1,
                "description": label,
                "sql_ref": f"reporting.compute_all::{mid}",
            }
            for mid, label in _METRICS
        ],
    )


def downgrade() -> None:
    Base.metadata.drop_all(bind=op.get_bind())
