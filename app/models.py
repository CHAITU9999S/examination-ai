
from datetime import datetime, timezone
from enum import Enum as PythonEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum as SQLAlchemyEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship, synonym

from app.database import Base


# -----------------------------------------
# DATABASE ENUMERATIONS
# -----------------------------------------

class QuestionType(str, PythonEnum):
    MCQ = "MCQ"
    MULTI_SELECT = "multi_select"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    IMAGE_UPLOAD = "image_upload"


class DifficultyLevel(str, PythonEnum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExamStatus(str, PythonEnum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SessionStatus(str, PythonEnum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"
    EXPIRED = "expired"


class AnswerStatus(str, PythonEnum):
    NOT_ANSWERED = "not_answered"
    ANSWERED = "answered"
    PENDING_REVIEW = "pending_review"
    GRADED = "graded"


def utc_now_naive():
    """Return the current UTC time without timezone information."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


# -----------------------------------------
# USERS TABLE
# -----------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(150), nullable=False)

    email = Column(
        String(255),
        unique=True,
        nullable=False
    )

    department = Column(String(100), nullable=True)

    password_hash = Column(String(255), nullable=False)

    # Compatibility with existing authentication code.
    hashed_password = synonym("password_hash")

    role = Column(String(20), nullable=False)

    is_active = Column(
        Boolean,
        default=True,
        nullable=True
    )

    created_at = Column(
        DateTime(),
        default=utc_now_naive,
        nullable=True
    )

    created_exams = relationship(
        "Exam",
        back_populates="examiner",
        foreign_keys="Exam.created_by"
    )

    questions = relationship(
        "Question",
        back_populates="creator"
    )

    exam_sessions = relationship(
        "ExamSession",
        back_populates="student"
    )

    admin_actions = relationship(
        "AdminActivityLog",
        back_populates="actor",
        foreign_keys="AdminActivityLog.actor_user_id"
    )

    admin_targets = relationship(
        "AdminActivityLog",
        back_populates="target",
        foreign_keys="AdminActivityLog.target_user_id"
    )

    __table_args__ = (
        Index("ix_users_email", "email"),
    )


# -----------------------------------------
# QUESTION BANK TABLE
# -----------------------------------------

class Question(Base):
    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, index=True)

    question_text = Column(Text, nullable=False)

    question_type = Column(
        SQLAlchemyEnum(
            QuestionType,
            name="question_type_enum",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
            validate_strings=True
        ),
        nullable=False
    )

    subject = Column(String(100), nullable=True)

    difficulty = Column(String(20), nullable=True)

    expected_answer = Column(Text, nullable=True)

    model_answer_text = Column(Text, nullable=True)

    # Compatibility with existing code using model_answer.
    model_answer = synonym("model_answer_text")

    marks = Column(Float, nullable=True)

    negative_marks = Column(Float, nullable=True)

    tags = Column(JSON, nullable=True)

    # Compatibility with existing code using keywords.
    keywords = synonym("tags")

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    creator = relationship(
        "User",
        back_populates="questions"
    )

    options = relationship(
        "Option",
        back_populates="question",
        cascade="all, delete-orphan"
    )

    exam_questions = relationship(
        "ExamQuestion",
        back_populates="question"
    )

    answers = relationship(
        "Answer",
        back_populates="question"
    )


# -----------------------------------------
# QUESTION OPTIONS TABLE
# -----------------------------------------

class Option(Base):
    __tablename__ = "options"

    id = Column(Integer, primary_key=True, index=True)

    question_id = Column(
        Integer,
        ForeignKey("question_bank.id", ondelete="CASCADE"),
        nullable=False
    )

    option_text = Column(Text, nullable=False)

    is_correct = Column(Boolean, nullable=True)

    question = relationship(
        "Question",
        back_populates="options"
    )


# -----------------------------------------
# EXAMS TABLE
# -----------------------------------------

class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)

    title = Column(String(200), nullable=False)

    subject = Column(String(100), nullable=True)

    duration_minutes = Column(Integer, nullable=False)

    total_questions = Column(Integer, nullable=True)

    randomize_questions = Column(Boolean, nullable=True)

    selection_rules = Column(JSON, nullable=True)

    # Compatibility with existing configuration code.
    configuration = synonym("selection_rules")

    start_time = Column(DateTime(), nullable=True)

    end_time = Column(DateTime(), nullable=True)

    negative_marking = Column(Boolean, nullable=True)

    # Compatibility with existing code.
    negative_marking_enabled = synonym("negative_marking")

    proctoring_enabled = Column(Boolean, nullable=True)

    gaze_tracking_sensitivity = Column(Float, nullable=True)

    max_tab_switch_warnings = Column(Integer, nullable=True)

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    # Compatibility with existing code using examiner_id.
    examiner_id = synonym("created_by")

    examiner = relationship(
        "User",
        back_populates="created_exams",
        foreign_keys=[created_by]
    )

    exam_questions = relationship(
        "ExamQuestion",
        back_populates="exam",
        cascade="all, delete-orphan"
    )

    exam_sessions = relationship(
        "ExamSession",
        back_populates="exam"
    )


# -----------------------------------------
# EXAM QUESTIONS TABLE
# -----------------------------------------

class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id = Column(Integer, primary_key=True, index=True)

    exam_id = Column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False
    )

    question_id = Column(
        Integer,
        ForeignKey("question_bank.id"),
        nullable=False
    )

    question_order = Column(Integer, nullable=True)

    exam = relationship(
        "Exam",
        back_populates="exam_questions"
    )

    question = relationship(
        "Question",
        back_populates="exam_questions"
    )

    __table_args__ = (
        UniqueConstraint(
            "exam_id",
            "question_id"
        ),
    )


# -----------------------------------------
# EXAM SESSIONS TABLE
# -----------------------------------------

class ExamSession(Base):
    __tablename__ = "exam_sessions"

    id = Column(Integer, primary_key=True, index=True)

    exam_id = Column(
        Integer,
        ForeignKey("exams.id"),
        nullable=False
    )

    student_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    started_at = Column(DateTime(), nullable=True)

    submitted_at = Column(DateTime(), nullable=True)

    status = Column(
        String(20),
        default=SessionStatus.NOT_STARTED.value,
        nullable=True
    )

    suspicion_score = Column(Float, nullable=True)

    expires_at = Column(
        DateTime(),
        nullable=False
    )

    last_heartbeat_at = Column(DateTime(), nullable=True)
    last_heartbeat_signals = Column(JSON, nullable=True)

    selected_question_ids = Column(
        JSON,
        nullable=True
    )

    student = relationship(
        "User",
        back_populates="exam_sessions"
    )

    exam = relationship(
        "Exam",
        back_populates="exam_sessions"
    )

    answers = relationship(
        "Answer",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    proctor_events = relationship(
        "ProctorEvent",
        back_populates="session",
        cascade="all, delete-orphan"
    )

    result = relationship(
        "Result",
        back_populates="session",
        uselist=False
    )

    __table_args__ = (
        Index(
            "uq_exam_sessions_active_student_exam",
            "exam_id",
            "student_id",
            unique=True,
            postgresql_where=text("status = 'in_progress'"),
            sqlite_where=text("status = 'in_progress'")
        ),
    )


# -----------------------------------------
# ANSWERS TABLE
# -----------------------------------------

class Answer(Base):
    __tablename__ = "answers"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("exam_sessions.id"),
        nullable=False
    )

    question_id = Column(
        Integer,
        ForeignKey("question_bank.id"),
        nullable=False
    )

    answer_text = Column(Text, nullable=True)

    image_path = Column(String(500), nullable=True)

    # Compatibility with existing answer-handling code.
    uploaded_file_path = synonym("image_path")

    awarded_marks = Column(Float, nullable=True)

    ai_suggested_marks = Column(Float, nullable=True)

    ai_justification = Column(Text, nullable=True)

    ai_matched_points = Column(JSON, nullable=True)

    ai_missed_points = Column(JSON, nullable=True)

    ai_model = Column(String(100), nullable=True)

    ai_suggestion_generated_at = Column(DateTime(), nullable=True)

    # Compatibility with existing evaluation code.
    marks_awarded = synonym("awarded_marks")

    session = relationship(
        "ExamSession",
        back_populates="answers"
    )

    question = relationship(
        "Question",
        back_populates="answers"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_id",
            name="uq_answers_session_question"
        ),
    )


# -----------------------------------------
# RESULTS TABLE
# -----------------------------------------

class Result(Base):
    __tablename__ = "results"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("exam_sessions.id"),
        nullable=False,
        unique=True
    )

    total_marks = Column(Float, nullable=True)

    obtained_marks = Column(Float, nullable=True)

    # Per-question score breakdown required for result review.
    question_scores = Column(JSON, nullable=True)

    # Compatibility with existing result-handling code.
    marks_obtained = synonym("obtained_marks")

    percentage = Column(Float, nullable=True)

    evaluated_at = Column(DateTime(), nullable=True)

    session = relationship(
        "ExamSession",
        back_populates="result"
    )


# -----------------------------------------
# PROCTOR EVENTS TABLE
# -----------------------------------------

class ProctorEvent(Base):
    __tablename__ = "proctor_events"

    id = Column(Integer, primary_key=True, index=True)

    session_id = Column(
        Integer,
        ForeignKey("exam_sessions.id"),
        nullable=False
    )

    event_type = Column(String(100), nullable=False)

    description = Column(Text, nullable=True)

    suspicion_points = Column(Float, nullable=True)

    # Running server-calculated session score immediately after this event.
    cumulative_suspicion_score = Column(
        Float,
        nullable=False,
        default=0,
        server_default=text("0"),
    )

    # Compatibility with existing proctoring code.
    suspicion_score = synonym("suspicion_points")

    created_at = Column(
        DateTime(),
        default=utc_now_naive,
        nullable=True
    )

    # Compatibility with existing code.
    recorded_at = synonym("created_at")

    snapshot_data = Column(Text, nullable=True)

    gaze_data = Column(JSON, nullable=True)

    tab_switch_count = Column(Integer, nullable=True)

    session = relationship(
        "ExamSession",
        back_populates="proctor_events"
    )


# -----------------------------------------
# ADMIN ACTIVITY LOGS TABLE
# -----------------------------------------

class AdminActivityLog(Base):
    __tablename__ = "admin_activity_logs"

    id = Column(Integer, primary_key=True, index=True)

    actor_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    target_user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )

    action = Column(String(100), nullable=False)

    details = Column(JSON, nullable=True)

    created_at = Column(
        DateTime(),
        nullable=False,
        server_default=text("now()")
    )

    actor = relationship(
        "User",
        back_populates="admin_actions",
        foreign_keys=[actor_user_id]
    )

    target = relationship(
        "User",
        back_populates="admin_targets",
        foreign_keys=[target_user_id]
    )


# -----------------------------------------
# BACKWARD-COMPATIBILITY ALIASES
# -----------------------------------------

QuestionBank = Question
