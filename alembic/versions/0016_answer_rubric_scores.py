"""Add saved examiner rubric breakdowns to answers."""

from alembic import op
import sqlalchemy as sa


revision = "0016_answer_rubric_scores"
down_revision = "0015_result_publication_feedback"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "answers",
        sa.Column("rubric_scores", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("answers", "rubric_scores")
