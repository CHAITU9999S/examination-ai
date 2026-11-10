from alembic import op

revision = "0003_question_type_enum"
down_revision = "0002_proctor_fields"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TYPE question_type_enum AS ENUM (
            'MCQ',
            'multi_select',
            'short_answer',
            'long_answer',
            'image_upload'
        );
    """)

    op.execute("""
        ALTER TABLE question_bank
        ALTER COLUMN question_type
        TYPE question_type_enum
        USING question_type::text::question_type_enum;
    """)


def downgrade():
    op.execute("""
        ALTER TABLE question_bank
        ALTER COLUMN question_type
        TYPE VARCHAR(30)
        USING question_type::text;
    """)

    op.execute("DROP TYPE question_type_enum;")
