"""users 테이블 + sessions.owner_id

Revision ID: 0002
Revises: 0001
Create Date: 2026-05-25

기존 owner 없는 sessions 는 마이그레이션 후 첫 register 된 user 에게 자동 귀속
(귀속 로직은 backend 의 auth.register 가 처리 — 이 마이그레이션은 nullable 컬럼만 추가).
"""

from typing import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.add_column(
        "sessions",
        sa.Column(
            "owner_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_index("ix_sessions_owner_id", "sessions", ["owner_id"])


def downgrade() -> None:
    op.drop_index("ix_sessions_owner_id", table_name="sessions")
    op.drop_column("sessions", "owner_id")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
