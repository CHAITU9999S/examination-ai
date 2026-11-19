"""Store question and answer image bytes in PostgreSQL.

Revision ID: 0018_neon_image_storage
Revises: 0017_question_prompt_image
"""
from alembic import op
import sqlalchemy as sa


revision = "0018_neon_image_storage"
down_revision = "0017_question_prompt_image"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question_bank",
        sa.Column("question_image_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "question_bank",
        sa.Column("question_image_mime_type", sa.String(length=50), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("image_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("thumbnail_data", sa.LargeBinary(), nullable=True),
    )
    op.add_column(
        "answers",
        sa.Column("image_mime_type", sa.String(length=50), nullable=True),
    )


def downgrade():
    op.drop_column("answers", "image_mime_type")
    op.drop_column("answers", "thumbnail_data")
    op.drop_column("answers", "image_data")
    op.drop_column("question_bank", "question_image_mime_type")
    op.drop_column("question_bank", "question_image_data")
