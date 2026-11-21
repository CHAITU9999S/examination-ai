"""Add named question banks."""

from alembic import op
import sqlalchemy as sa


revision = "0022_named_question_banks"
down_revision = "0021_exam_question_marks_revisions"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "question_collections",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=150), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=True),
        sa.Column("subject", sa.String(length=100), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_question_collections_id", "question_collections", ["id"])

    op.create_table(
        "question_collection_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("collection_id", sa.Integer(), sa.ForeignKey("question_collections.id", ondelete="CASCADE"), nullable=False),
        sa.Column("question_id", sa.Integer(), sa.ForeignKey("question_bank.id", ondelete="CASCADE"), nullable=False),
        sa.UniqueConstraint("collection_id", "question_id", name="uq_question_collection_item"),
    )
    op.create_index("ix_question_collection_items_id", "question_collection_items", ["id"])


def downgrade():
    op.drop_index("ix_question_collection_items_id", table_name="question_collection_items")
    op.drop_table("question_collection_items")
    op.drop_index("ix_question_collections_id", table_name="question_collections")
    op.drop_table("question_collections")
