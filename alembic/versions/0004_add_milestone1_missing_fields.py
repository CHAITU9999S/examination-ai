from alembic import op
import sqlalchemy as sa


revision = "0004_add_milestone1_missing_fields"
down_revision = "0003_question_type_enum"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "question_bank",
        sa.Column("model_answer_text", sa.Text(), nullable=True)
    )

    op.add_column(
        "exams",
        sa.Column("gaze_tracking_sensitivity", sa.Float(), nullable=True)
    )

    op.add_column(
        "exams",
        sa.Column("max_tab_switch_warnings", sa.Integer(), nullable=True)
    )


def downgrade():
    op.drop_column("exams", "max_tab_switch_warnings")
    op.drop_column("exams", "gaze_tracking_sensitivity")
    op.drop_column("question_bank", "model_answer_text")
