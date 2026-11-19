"""Add result publication and examiner feedback fields.

This migration is additive. It preserves existing answers and results.
"""

from alembic import op
import sqlalchemy as sa


revision = "0015_result_publication_feedback"
down_revision = "0014_exam_token_refresh"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "results",
        sa.Column(
            "is_published",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "results",
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("examiner_feedback", sa.Text(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("image_annotations", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("answers", "image_annotations")
    op.drop_column("answers", "examiner_feedback")
    op.drop_column("results", "published_at")
    op.drop_column("results", "is_published")
