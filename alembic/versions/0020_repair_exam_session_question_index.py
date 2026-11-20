"""Repair the missing exam session question index column.

Revision ID: 0020_repair_exam_session_question_index
Revises: 0019_exam_workflow_features

This is a schema-drift repair: migration 0019 is recorded as applied,
but some databases may be missing the column it was meant to create.
"""
from alembic import op
import sqlalchemy as sa


revision = "0020_repair_exam_session_question_index"
down_revision = "0019_exam_workflow_features"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    existing_columns = {
        column["name"]
        for column in sa.inspect(bind).get_columns("exam_sessions", schema="public")
    }

    if "current_question_index" not in existing_columns:
        op.add_column(
            "exam_sessions",
            sa.Column(
                "current_question_index",
                sa.Integer(),
                nullable=False,
                server_default=sa.text("0"),
            ),
            schema="public",
        )


def downgrade():
    # Intentionally retain this repair column. Some databases may have had
    # the column before this corrective revision; dropping it on downgrade
    # could remove valid application data or break the exam-session model.
    pass
