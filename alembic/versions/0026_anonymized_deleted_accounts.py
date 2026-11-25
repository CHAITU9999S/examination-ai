"""Track anonymized deleted accounts while preserving historical records."""

from alembic import op
import sqlalchemy as sa


revision = "0026_anonymized_deleted_accounts"
down_revision = "0025_exam_prestart_and_face_capture"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column(
            "is_deleted",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("users", "deleted_at")
    op.drop_column("users", "is_deleted")
