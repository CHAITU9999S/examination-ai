"""Persist examination entry stages and candidate face captures."""

from alembic import op
import sqlalchemy as sa


revision = "0025_exam_prestart_and_face_capture"
down_revision = "0024_platform_settings"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column(
        "exam_sessions",
        "expires_at",
        existing_type=sa.DateTime(),
        nullable=True,
    )
    op.add_column("exam_sessions", sa.Column("prestart_stage", sa.String(length=20), nullable=True))
    op.add_column("exam_sessions", sa.Column("prestart_expires_at", sa.DateTime(), nullable=True))
    op.add_column("exam_sessions", sa.Column("summary_started_at", sa.DateTime(), nullable=True))
    op.add_column("exam_sessions", sa.Column("start_window_expires_at", sa.DateTime(), nullable=True))
    op.add_column("exam_sessions", sa.Column("face_capture_data", sa.LargeBinary(), nullable=True))
    op.add_column("exam_sessions", sa.Column("face_capture_mime_type", sa.String(length=50), nullable=True))
    op.add_column("exam_sessions", sa.Column("face_captured_at", sa.DateTime(), nullable=True))


def downgrade():
    # Restore a non-null deadline before reverting the legacy column constraint.
    connection = op.get_bind()
    connection.execute(
        sa.text(
            "UPDATE exam_sessions SET expires_at = COALESCE(expires_at, prestart_expires_at, CURRENT_TIMESTAMP) "
            "WHERE expires_at IS NULL"
        )
    )
    op.drop_column("exam_sessions", "face_captured_at")
    op.drop_column("exam_sessions", "face_capture_mime_type")
    op.drop_column("exam_sessions", "face_capture_data")
    op.drop_column("exam_sessions", "start_window_expires_at")
    op.drop_column("exam_sessions", "summary_started_at")
    op.drop_column("exam_sessions", "prestart_expires_at")
    op.drop_column("exam_sessions", "prestart_stage")
    op.alter_column(
        "exam_sessions",
        "expires_at",
        existing_type=sa.DateTime(),
        nullable=False,
    )
