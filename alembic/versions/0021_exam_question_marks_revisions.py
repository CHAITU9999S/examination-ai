"""Add separate question paper marks revision history.

Revision ID: 0021_exam_question_marks_revisions
Revises: 0020_repair_exam_session_question_index
"""
from alembic import op
import sqlalchemy as sa


revision = "0021_exam_question_marks_revisions"
down_revision = "0020_repair_exam_session_question_index"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "exam_question_marks_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("marks_snapshot", sa.JSON(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("exam_id", "revision_number", name="uq_exam_question_marks_revision"),
    )
    op.create_index(
        "ix_exam_question_marks_revisions_id",
        "exam_question_marks_revisions",
        ["id"],
    )


def downgrade():
    op.drop_index("ix_exam_question_marks_revisions_id", table_name="exam_question_marks_revisions")
    op.drop_table("exam_question_marks_revisions")
