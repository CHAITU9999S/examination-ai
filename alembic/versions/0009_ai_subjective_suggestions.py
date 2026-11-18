from alembic import op
import sqlalchemy as sa


revision = "0009_ai_subjective_suggestions"
down_revision = "0008_store_session_question_selection"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "answers",
        sa.Column("ai_suggested_marks", sa.Float(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("ai_justification", sa.Text(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("ai_matched_points", sa.JSON(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("ai_missed_points", sa.JSON(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("ai_model", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("ai_suggestion_generated_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("answers", "ai_suggestion_generated_at")
    op.drop_column("answers", "ai_model")
    op.drop_column("answers", "ai_missed_points")
    op.drop_column("answers", "ai_matched_points")
    op.drop_column("answers", "ai_justification")
    op.drop_column("answers", "ai_suggested_marks")
