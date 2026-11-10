from alembic import op
import sqlalchemy as sa

revision = "0003_question_type_enum"
down_revision = "0002_proctor_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        ALTER TABLE question_bank
        ALTER COLUMN question_type TYPE VARCHAR(30);
    """)

    op.execute("""
        ALTER TABLE question_bank
        ADD CONSTRAINT question_type_enum_check
        CHECK (
            question_type IN (
                'MCQ',
                'multi_select',
                'short_answer',
                'long_answer',
                'image_upload'
            )
        );
    """)


def downgrade():
    op.drop_constraint(
        "question_type_enum_check",
        "question_bank",
        type_="check"
    )
