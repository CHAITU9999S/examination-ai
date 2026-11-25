"""Persist visited question navigation state for exam sessions."""

from alembic import op
import sqlalchemy as sa


revision = "0030_exam_session_navigation"
down_revision = "0029_account_management"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exam_sessions",
        sa.Column("visited_question_ids", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("exam_sessions", "visited_question_ids")
