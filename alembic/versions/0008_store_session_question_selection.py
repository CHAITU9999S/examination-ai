from alembic import op
import sqlalchemy as sa


revision = "0008_store_session_question_selection"
down_revision = "0007_unique_session_question_answers"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "exam_sessions",
        sa.Column(
            "selected_question_ids",
            sa.JSON(),
            nullable=True
        )
    )


def downgrade():
    op.drop_column(
        "exam_sessions",
        "selected_question_ids"
    )
  
