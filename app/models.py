
from datetime import datetime

from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, Enum,
    ForeignKey, Text, Float, JSON, UniqueConstraint
)
from sqlalchemy.orm import relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    full_name = Column(String(150), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    department = Column(String(100))
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), nullable=False, default="student")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class QuestionBank(Base):
    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False)
    question_type = Column(
        Enum(
            "MCQ",
            "multi_select",
            "short_answer",
            "long_answer",
            "image_upload",
            name="question_type_enum"
        ),
        nullable=False
    )
    subject = Column(String(100))
    difficulty = Column(String(20))
    expected_answer = Column(Text)
    model_answer_text = Column(Text, nullable=True)
    marks = Column(Float, default=1)
    negative_marks = Column(Float, default=0)
    tags = Column(JSON)
    created_by = Column(Integer, ForeignKey("users.id"))


class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(
        Integer, ForeignKey("question_bank.id", ondelete="CASCADE"),
        nullable=False
    )
    option_text = Column(Text, nullable=False)
    is_correct = Column(Boolean, default=False)


class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), nullable=False)
    subject = Column(String(100))
    duration_minutes = Column(Integer, nullable=False)
    total_questions = Column(Integer, default=0)
    randomize_questions = Column(Boolean, default=True)
    selection_rules = Column(JSON, nullable=True)
    start_time = Column(DateTime)
    end_time = Column(DateTime)
    negative_marking = Column(Boolean, default=False)
    proctoring_enabled = Column(Boolean, default=True)
    gaze_tracking_sensitivity = Column(Float, nullable=True)
    max_tab_switch_warnings = Column(Integer, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"))


class ExamQuestion(Base):
    __tablename__ = "exam_questions"
    __table_args__ = (
        UniqueConstraint("exam_id", "question_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    question_id = Column(
        Integer, ForeignKey("question_bank.id"), nullable=False
    )
    question_order = Column(Integer)


class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)
    exam_id = Column(Integer, ForeignKey("exams.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    submitted_at = Column(DateTime)
    status = Column(String(20), default="in_progress")
    suspicion_score = Column(Float, default=0)


class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("exam_sessions.id"), nullable=False
    )
    question_id = Column(
        Integer, ForeignKey("question_bank.id"), nullable=False
    )
    answer_text = Column(Text)
    image_path = Column(String(500))
    awarded_marks = Column(Float)


class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("exam_sessions.id"), unique=True,
        nullable=False
    )
    total_marks = Column(Float, default=0)
    obtained_marks = Column(Float, default=0)
    percentage = Column(Float, default=0)
    evaluated_at = Column(DateTime, default=datetime.utcnow)


class ProctorEvent(Base):
    __tablename__ = "proctor_events"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(
        Integer, ForeignKey("exam_sessions.id"), nullable=False
    )
    event_type = Column(String(100), nullable=False)
    description = Column(Text)
    snapshot_data = Column(Text, nullable=True)
    gaze_data = Column(JSON, nullable=True)
    tab_switch_count = Column(Integer, default=0)
    suspicion_points = Column(Float, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    
