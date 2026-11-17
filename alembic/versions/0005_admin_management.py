
from alembic import op
import sqlalchemy as sa


revision = "0005_admin_management"
down_revision = "0004_m1_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "admin_activity_logs",

        sa.Column(
            "id",
            sa.Integer(),
            primary_key=True
        ),

        sa.Column(
            "actor_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=False
        ),

        sa.Column(
            "target_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id"),
            nullable=True
        ),

        sa.Column(
            "action",
            sa.String(length=100),
            nullable=False
        ),

        sa.Column(
            "details",
            sa.JSON(),
            nullable=True
        ),

        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.func.now()
        )
    )

    op.create_index(
        "ix_admin_activity_logs_actor_user_id",
        "admin_activity_logs",
        ["actor_user_id"]
    )

    op.create_index(
        "ix_admin_activity_logs_target_user_id",
        "admin_activity_logs",
        ["target_user_id"]
    )

    op.create_index(
        "ix_admin_activity_logs_created_at",
        "admin_activity_logs",
        ["created_at"]
    )


def downgrade():
    op.drop_index(
        "ix_admin_activity_logs_created_at",
        table_name="admin_activity_logs"
    )

    op.drop_index(
        "ix_admin_activity_logs_target_user_id",
        table_name="admin_activity_logs"
    )

    op.drop_index(
        "ix_admin_activity_logs_actor_user_id",
        table_name="admin_activity_logs"
    )

    op.drop_table("admin_activity_logs")
          
