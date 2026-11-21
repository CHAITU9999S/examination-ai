"""Named question banks that can be reused across examinations."""

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.sql import func

from app.database import Base


class QuestionCollection(Base):
    __tablename__ = "question_collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(150), nullable=False)
    description = Column(String(500), nullable=True)
    subject = Column(String(100), nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime(), nullable=False, server_default=func.now())


class QuestionCollectionItem(Base):
    __tablename__ = "question_collection_items"

    id = Column(Integer, primary_key=True, index=True)
    collection_id = Column(
        Integer,
        ForeignKey("question_collections.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_id = Column(
        Integer,
        ForeignKey("question_bank.id", ondelete="CASCADE"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "collection_id",
            "question_id",
            name="uq_question_collection_item",
        ),
    )
