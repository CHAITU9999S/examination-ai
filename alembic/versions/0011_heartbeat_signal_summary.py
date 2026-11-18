from alembic import op
import sqlalchemy as sa


revision = "0011_heartbeat_signal_summary"
down_revision = "0010_exam_session_heartbeat"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exam_sessions",
        sa.Column("last_heartbeat_signals", sa.JSON(), nullable=True),
    )


def downgrade():
    op.drop_column("exam_sessions", "last_heartbeat_signals")
