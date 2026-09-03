"""hash session tokens

Revision ID: 0007_hash_session_tokens
Revises: 0006_notifications
Create Date: 2026-09-03

user_session.token_id now stores SHA-256(token) instead of the raw cookie value
(finding #5). Existing rows hold raw values that can no longer be matched, so
clear them - every active session is invalidated and users sign in again once.
No schema change; the column already fits a 64-char hex digest.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0007_hash_session_tokens"
down_revision = "0006_notifications"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def upgrade() -> None:
    if _has_table("user_session"):
        op.execute("DELETE FROM user_session")


def downgrade() -> None:
    # Irreversible in practice (the raw tokens are gone); clearing again is the
    # closest safe equivalent.
    if _has_table("user_session"):
        op.execute("DELETE FROM user_session")
