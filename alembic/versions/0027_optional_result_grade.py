"""Add optional examiner-assigned result grade."""

from alembic import op
import sqlalchemy as sa


revision = "0027_optional_result_grade"
down_revision = "0026_anonymized_deleted_accounts"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("results", sa.Column("grade", sa.String(length=20), nullable=True))


def downgrade():
    op.drop_column("results", "grade")
