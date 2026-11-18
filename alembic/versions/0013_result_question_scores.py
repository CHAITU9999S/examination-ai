"""Add per-question score breakdown to final results."""

from alembic import op
import sqlalchemy as sa


revision = "0013_result_question_scores"
down_revision = "0012_proctor_event_score_snapshot"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "results",
        sa.Column("question_scores", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("results", "question_scores")
