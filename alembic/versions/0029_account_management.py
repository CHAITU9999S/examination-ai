"""Add account profile editing limits and login history."""

from alembic import op
import sqlalchemy as sa


revision = "0029_account_management"
down_revision = "0028_merge_0027_heads"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("date_of_birth", sa.Date(), nullable=True))
    op.add_column("users", sa.Column("full_name_edit_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("email_edit_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("department_edit_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("users", sa.Column("date_of_birth_edit_count", sa.Integer(), nullable=False, server_default="0"))

    op.create_table(
        "login_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("logged_in_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("ip_address", sa.String(length=45), nullable=True),
        sa.Column("user_agent", sa.String(length=500), nullable=True),
    )
    op.create_index("ix_login_history_user_id", "login_history", ["user_id"])
    op.create_index("ix_login_history_user_logged_in_at", "login_history", ["user_id", "logged_in_at"])


def downgrade():
    op.drop_index("ix_login_history_user_logged_in_at", table_name="login_history")
    op.drop_index("ix_login_history_user_id", table_name="login_history")
    op.drop_table("login_history")
    op.drop_column("users", "date_of_birth_edit_count")
    op.drop_column("users", "department_edit_count")
    op.drop_column("users", "email_edit_count")
    op.drop_column("users", "full_name_edit_count")
    op.drop_column("users", "date_of_birth")
