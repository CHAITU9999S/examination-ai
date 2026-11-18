from alembic import op
import sqlalchemy as sa


revision = "0006_timed_exam_engine"
down_revision = "0005_admin_management"
branch_labels = None
depends_on = None


def upgrade():
    # Add the server-calculated deadline.
    op.add_column(
        "exam_sessions",
        sa.Column(
            "expires_at",
            sa.DateTime(),
            nullable=True
        )
    )

    # Backfill deadlines for all existing sessions.
    # Existing session start times and exam durations are preserved.
    op.execute(
        sa.text("""
            UPDATE exam_sessions AS session
            SET expires_at =
                COALESCE(session.started_at, CURRENT_TIMESTAMP)
                + (exam.duration_minutes * INTERVAL '1 minute')
            FROM exams AS exam
            WHERE session.exam_id = exam.id
        """)
    )

    # Make the deadline mandatory after backfilling.
    op.alter_column(
        "exam_sessions",
        "expires_at",
        existing_type=sa.DateTime(),
        nullable=False
    )

    # Prevent multiple active sessions for the same student and exam.
    op.create_index(
        "uq_exam_sessions_active_student_exam",
        "exam_sessions",
        ["exam_id", "student_id"],
        unique=True,
        postgresql_where=sa.text("status = 'in_progress'")
    )


def downgrade():
    op.drop_index(
        "uq_exam_sessions_active_student_exam",
        table_name="exam_sessions"
    )

    op.drop_column(
        "exam_sessions",
        "expires_at"
  )
  
