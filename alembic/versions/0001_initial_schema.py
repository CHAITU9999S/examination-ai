from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(150), nullable=False),
        sa.Column("email", sa.String(255), nullable=False, unique=True),
        sa.Column("department", sa.String(100)),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("is_active", sa.Boolean()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "question_bank",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_text", sa.Text(), nullable=False),
        sa.Column("question_type", sa.String(30), nullable=False),
        sa.Column("subject", sa.String(100)),
        sa.Column("difficulty", sa.String(20)),
        sa.Column("expected_answer", sa.Text()),
        sa.Column("marks", sa.Float()),
        sa.Column("negative_marks", sa.Float()),
        sa.Column("tags", sa.JSON()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_question_bank_id", "question_bank", ["id"])

    op.create_table(
        "options",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("question_id", sa.Integer(),
                  sa.ForeignKey("question_bank.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("option_text", sa.Text(), nullable=False),
        sa.Column("is_correct", sa.Boolean()),
    )
    op.create_index("ix_options_id", "options", ["id"])

    op.create_table(
        "exams",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("subject", sa.String(100)),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("total_questions", sa.Integer()),
        sa.Column("randomize_questions", sa.Boolean()),
        sa.Column("selection_rules", sa.JSON()),
        sa.Column("start_time", sa.DateTime()),
        sa.Column("end_time", sa.DateTime()),
        sa.Column("negative_marking", sa.Boolean()),
        sa.Column("proctoring_enabled", sa.Boolean()),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id")),
    )
    op.create_index("ix_exams_id", "exams", ["id"])

    op.create_table(
        "exam_questions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(),
                  sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("question_id", sa.Integer(),
                  sa.ForeignKey("question_bank.id"), nullable=False),
        sa.Column("question_order", sa.Integer()),
        sa.UniqueConstraint("exam_id", "question_id"),
    )
    op.create_index("ix_exam_questions_id", "exam_questions", ["id"])

    op.create_table(
        "exam_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("exam_id", sa.Integer(),
                  sa.ForeignKey("exams.id"), nullable=False),
        sa.Column("student_id", sa.Integer(),
                  sa.ForeignKey("users.id"), nullable=False),
        sa.Column("started_at", sa.DateTime()),
        sa.Column("submitted_at", sa.DateTime()),
        sa.Column("status", sa.String(20)),
        sa.Column("suspicion_score", sa.Float()),
    )
    op.create_index("ix_exam_sessions_id", "exam_sessions", ["id"])

    op.create_table(
        "answers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(),
                  sa.ForeignKey("exam_sessions.id"), nullable=False),
        sa.Column("question_id", sa.Integer(),
                  sa.ForeignKey("question_bank.id"), nullable=False),
        sa.Column("answer_text", sa.Text()),
        sa.Column("image_path", sa.String(500)),
        sa.Column("awarded_marks", sa.Float()),
    )
    op.create_index("ix_answers_id", "answers", ["id"])

    op.create_table(
        "results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(),
                  sa.ForeignKey("exam_sessions.id"),
                  unique=True, nullable=False),
        sa.Column("total_marks", sa.Float()),
        sa.Column("obtained_marks", sa.Float()),
        sa.Column("percentage", sa.Float()),
        sa.Column("evaluated_at", sa.DateTime()),
    )
    op.create_index("ix_results_id", "results", ["id"])

    op.create_table(
        "proctor_events",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(),
                  sa.ForeignKey("exam_sessions.id"), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("suspicion_points", sa.Float()),
        sa.Column("created_at", sa.DateTime()),
    )
    op.create_index("ix_proctor_events_id", "proctor_events", ["id"])


def downgrade():
    op.drop_table("proctor_events")
    op.drop_index("ix_results_id", table_name="results")
    op.drop_table("results")
    op.drop_index("ix_answers_id", table_name="answers")
    op.drop_table("answers")
    op.drop_index("ix_exam_sessions_id", table_name="exam_sessions")
    op.drop_table("exam_sessions")
    op.drop_index("ix_exam_questions_id", table_name="exam_questions")
    op.drop_table("exam_questions")
    op.drop_index("ix_exams_id", table_name="exams")
    op.drop_table("exams")
    op.drop_index("ix_options_id", table_name="options")
    op.drop_table("options")
    op.drop_index("ix_question_bank_id", table_name="question_bank")
    op.drop_table("question_bank")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
