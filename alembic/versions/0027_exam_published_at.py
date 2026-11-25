"""Record the date and time when an examination is published.

Revision ID: 0027_exam_published_at
Revises: 0026_anonymized_deleted_accounts
"""
from alembic import op
import sqlalchemy as sa


revision = "0027_exam_published_at"
down_revision = "0026_anonymized_deleted_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exams",
        sa.Column("published_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("exams", "published_at")
