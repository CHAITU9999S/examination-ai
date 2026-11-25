"""Merge the two independent 0027 migration heads.

This is a graph-only merge; both parent migrations are retained.
"""

revision = "0028_merge_0027_heads"
down_revision = ("0027_exam_published_at", "0027_optional_result_grade")
branch_labels = None
depends_on = None


def upgrade():
    pass


def downgrade():
    pass
