"""Add exam assignment, per-question timing, bank provenance and revision history.

Revision ID: 0019_exam_workflow_features
Revises: 0018_neon_image_storage
"""
from alembic import op
import sqlalchemy as sa


revision = "0019_exam_workflow_features"
down_revision = "0018_neon_image_storage"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question_bank",
        sa.Column(
            "source_question_id",
            sa.Integer(),
            sa.ForeignKey("question_bank.id"),
            nullable=True,
        ),
    )
    op.create_index(
        "ix_question_bank_source_question_id",
        "question_bank",
        ["source_question_id"],
    )

    op.add_column(
        "exam_questions",
        sa.Column("question_time_limit_seconds", sa.Integer(), nullable=True),
    )
    op.add_column(
        "exam_sessions",
        sa.Column(
            "is_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "exam_sessions",
        sa.Column("paused_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("question_started_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column(
            "question_elapsed_seconds",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "answers",
        sa.Column(
            "is_locked",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    op.create_table(
        "exam_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("student_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assigned_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.UniqueConstraint("exam_id", "student_id", name="uq_exam_assignment_student"),
    )
    op.create_index(
        "ix_exam_assignments_student_active",
        "exam_assignments",
        ["student_id", "is_active"],
    )

    op.create_table(
        "exam_configuration_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(), sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("configuration_snapshot", sa.JSON(), nullable=False),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("exam_id", "revision_number", name="uq_exam_config_revision"),
    )

    op.create_table(
        "answer_mark_revisions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("answer_id", sa.Integer(), sa.ForeignKey("answers.id"), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("previous_marks", sa.Float(), nullable=True),
        sa.Column("new_marks", sa.Float(), nullable=False),
        sa.Column("previous_feedback", sa.Text(), nullable=True),
        sa.Column("new_feedback", sa.Text(), nullable=True),
        sa.Column("revised_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.UniqueConstraint("answer_id", "revision_number", name="uq_answer_mark_revision"),
    )


def downgrade():
    op.drop_table("answer_mark_revisions")
    op.drop_table("exam_configuration_revisions")
    op.drop_index("ix_exam_assignments_student_active", table_name="exam_assignments")
    op.drop_table("exam_assignments")
    op.drop_column("answers", "is_locked")
    op.drop_column("answers", "question_elapsed_seconds")
    op.drop_column("answers", "question_started_at")
    op.drop_column("exam_sessions", "paused_at")
    op.drop_column("exam_sessions", "is_paused")
    op.drop_column("exam_questions", "question_time_limit_seconds")
    op.drop_index("ix_question_bank_source_question_id", table_name="question_bank")
    op.drop_column("question_bank", "source_question_id")
