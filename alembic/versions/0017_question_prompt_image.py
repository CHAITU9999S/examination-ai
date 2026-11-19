"""Add optional image path to question bank entries."""

from alembic import op
import sqlalchemy as sa


revision = "0017_question_prompt_image"
down_revision = "0016_answer_rubric_scores"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question_bank",
        sa.Column("question_image_path", sa.String(length=500), nullable=True),
    )


def downgrade():
    op.drop_column("question_bank", "question_image_path")
