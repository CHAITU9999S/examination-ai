"""Store optional expected-answer images in PostgreSQL."""

from alembic import op
import sqlalchemy as sa


revision = "0023_expected_answer_image"
down_revision = "0022_named_question_banks"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question_bank",
        sa.Column("expected_answer_image_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "question_bank",
        sa.Column("expected_answer_image_mime_type", sa.String(length=50), nullable=True),
    )


def downgrade():
    op.drop_column("question_bank", "expected_answer_image_mime_type")
    op.drop_column("question_bank", "expected_answer_image_data")
