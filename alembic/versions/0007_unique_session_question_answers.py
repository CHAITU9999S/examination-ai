from alembic import op
import sqlalchemy as sa


revision = "0007_unique_session_question_answers"
down_revision = "0006_timed_exam_engine"
branch_labels = None
depends_on = None


def upgrade():
    # Alembic's default version_num column is VARCHAR(32), but this
    # revision identifier is longer. Widen it before Alembic records
    # this revision so the version update does not fail on PostgreSQL.
    op.alter_column(
        "alembic_version",
        "version_num",
        existing_type=sa.String(length=32),
        type_=sa.String(length=128),
        existing_nullable=False
    )

    op.create_unique_constraint(
        "uq_answers_session_question",
        "answers",
        ["session_id", "question_id"]
    )


def downgrade():
    op.drop_constraint(
        "uq_answers_session_question",
        "answers",
        type_="unique"
    )
