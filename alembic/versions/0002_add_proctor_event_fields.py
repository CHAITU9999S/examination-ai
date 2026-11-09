from alembic import op
import sqlalchemy as sa

revision = "0002_proctor_fields"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "proctor_events",
        sa.Column("snapshot_data", sa.Text(), nullable=True)
    )
    op.add_column(
        "proctor_events",
        sa.Column("gaze_data", sa.JSON(), nullable=True)
    )
    op.add_column(
        "proctor_events",
        sa.Column("tab_switch_count", sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column("proctor_events", "tab_switch_count")
    op.drop_column("proctor_events", "gaze_data")
    op.drop_column("proctor_events", "snapshot_data")
  
