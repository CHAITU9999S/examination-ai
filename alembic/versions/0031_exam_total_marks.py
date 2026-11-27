"""Add exact total marks for unconfigured randomized exam papers."""

from alembic import op
import sqlalchemy as sa


revision = "0031_exam_total_marks"
down_revision = "0030_exam_session_navigation"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("exams", sa.Column("total_marks", sa.Float(), nullable=True))


def downgrade():
    op.drop_column("exams", "total_marks")
