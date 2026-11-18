from alembic import op
import sqlalchemy as sa


revision = "0010_exam_session_heartbeat"
down_revision = "0009_ai_subjective_suggestions"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exam_sessions",
        sa.Column("last_heartbeat_at", sa.DateTime(), nullable=True),
    )


def downgrade():
    op.drop_column("exam_sessions", "last_heartbeat_at")
