"""Add persistent platform settings for one-time administrative actions."""

from alembic import op
import sqlalchemy as sa


revision = "0024_platform_settings"
down_revision = "0022_user_active_device_session"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "platform_settings",
        sa.Column("setting_key", sa.String(length=100), primary_key=True),
        sa.Column("setting_value", sa.String(length=500), nullable=False),
        sa.Column(
            "updated_by",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.bulk_insert(
        sa.table(
            "platform_settings",
            sa.column("setting_key", sa.String(length=100)),
            sa.column("setting_value", sa.String(length=500)),
        ),
        [{"setting_key": "all_questions_deleted_once", "setting_value": "false"}],
    )


def downgrade():
    op.drop_table("platform_settings")
