"""Add one-active-device session identifier to users.

Revision ID: 0022_user_active_device_session
Revises: 0021_exam_question_marks_revisions
"""
import secrets

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
        unique=False,
    )

    # Force existing logins to authenticate again after this policy is
    # introduced. A unique random value makes every pre-migration JWT stale.
    connection = op.get_bind()
    users = sa.table(
        "users",
        sa.column("id", sa.Integer()),
        sa.column("active_session_id", sa.String(length=64)),
    )
    for user_id in connection.execute(
        sa.select(users.c.id)
    ).scalars():
        connection.execute(
            users.update()
            .where(users.c.id == user_id)
            .values(active_session_id=secrets.token_urlsafe(32))
        )

    # Existing examination refresh credentials must also be revoked. The
    # examination sessions and saved answers themselves are intentionally kept.
    exam_sessions = sa.table(
        "exam_sessions",
        sa.column("status", sa.String(length=20)),
        sa.column("exam_token_refresh_hash", sa.String(length=64)),
    )
    connection.execute(
        exam_sessions.update()
        .where(exam_sessions.c.status == "in_progress")
        .values(exam_token_refresh_hash=None)
    )


def downgrade():
    op.drop_index("ix_users_active_session_id", table_name="users")
    op.drop_column("users", "active_session_id")
