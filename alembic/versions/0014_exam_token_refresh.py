"""Store hashed rotating exam refresh tokens."""

from alembic import op
import sqlalchemy as sa


revision = "0014_exam_token_refresh"
down_revision = "0013_result_question_scores"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exam_sessions",
        sa.Column(
            "exam_token_refresh_hash",
            sa.String(length=64),
            nullable=True,
        ),
    )


def downgrade():
    op.drop_column("exam_sessions", "exam_token_refresh_hash")
