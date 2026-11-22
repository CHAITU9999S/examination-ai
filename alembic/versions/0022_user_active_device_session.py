"""Add one-active-device session identifier to users.

Revision ID: 0022_user_active_device_session
Revises: 0021_exam_question_marks_revisions
"""
from alembic import op
import sqlalchemy as sa


revision = "0022_user_active_device_session"
down_revision = "0021_exam_question_marks_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("active_session_id", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_users_active_session_id",
        "users",
        ["active_session_id"],
        unique=True,
    )


def downgrade():
    op.drop_index("ix_users_active_session_id", table_name="users")
    op.drop_column("users", "active_session_id")
