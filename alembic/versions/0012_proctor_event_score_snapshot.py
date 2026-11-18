"""Persist the cumulative suspicion score on every proctoring event."""

from alembic import op
import sqlalchemy as sa


revision = "0012_proctor_event_score_snapshot"
down_revision = "0011_heartbeat_signal_summary"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "proctor_events",
        sa.Column(
            "cumulative_suspicion_score",
            sa.Float(),
            nullable=False,
            server_default=sa.text("0"),
        ),
    )


def downgrade():
    op.drop_column(
        "proctor_events",
        "cumulative_suspicion_score",
    )
