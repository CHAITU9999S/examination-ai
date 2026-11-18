from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.database import Base
from app.schemas import UserRole


# -----------------------------------------
# DATABASE ENUMERATIONS
# -----------------------------------------

class QuestionType(str, __import__("enum").Enum):
    MCQ = "mcq"
    MULTI_SELECT = "multi_select"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    IMAGE_UPLOAD = "image_upload"


class DifficultyLevel(str, __import__("enum").Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class ExamStatus(str, __import__("enum").Enum):
    DRAFT = "draft"
    SCHEDULED = "scheduled"
    ACTIVE = "active"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class SessionStatus(str, __import__("enum").Enum):
    NOT_STARTED = "not_started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    AUTO_SUBMITTED = "auto_submitted"
    EXPIRED = "expired"


class AnswerStatus(str, __import__("enum").Enum):
    NOT_ANSWERED = "not_answered"
    ANSWERED = "answered"
    PENDING_REVIEW = "pending_review"
    GRADED = "graded"


# -----------------------------------------
# USERS TABLE
# -----------------------------------------

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)

    full_name = Column(String(100), nullable=False)

    email = Column(
        String(255),
        unique=True,
        index=True,
        nullable=False
    )

    hashed_password = Column(String(255), nullable=False)

    role = Column(
        Enum(
            UserRole,
            name="user_role",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        nullable=False
    )

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    created_exams = relationship(
        "Exam",
        back_populates="examiner",
        foreign_keys="Exam.examiner_id"
    )

    questions = relationship(
        "Question",
        back_populates="creator"
    )

    exam_sessions = relationship(
        "ExamSession",
        back_populates="student"
    )


# -----------------------------------------
# QUESTION BANK TABLE
# -----------------------------------------

class Question(Base):
    __tablename__ = "question_bank"

    id = Column(Integer, primary_key=True, index=True)

    created_by = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    question_text = Column(Text, nullable=False)

    question_type = Column(
        Enum(
            QuestionType,
            name="question_type",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        nullable=False
    )

    subject = Column(String(100), nullable=False, index=True)

    topic = Column(String(150), nullable=True)

    difficulty = Column(
        Enum(
            DifficultyLevel,
            name="difficulty_level",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        nullable=False
    )

    # Stores question options and their correctness information.
    # Example: [{"text": "Option A", "is_correct": true}]
    options = Column(JSON, nullable=True)

    expected_answer = Column(Text, nullable=True)

    model_answer = Column(Text, nullable=True)

    keywords = Column(JSON, nullable=True)

    marks = Column(Float, nullable=False, default=1.0)

    negative_marks = Column(Float, nullable=False, default=0.0)

    image_url = Column(String(500), nullable=True)

    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    creator = relationship(
        "User",
        back_populates="questions"
    )

    exam_questions = relationship(
        "ExamQuestion",
        back_populates="question"
    )

    __table_args__ = (
        CheckConstraint("marks > 0", name="check_question_marks"),
        CheckConstraint(
            "negative_marks >= 0",
            name="check_negative_marks"
        ),
    )


# -----------------------------------------
# EXAMS TABLE
# -----------------------------------------

class Exam(Base):
    __tablename__ = "exams"

    id = Column(Integer, primary_key=True, index=True)

    examiner_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False
    )

    title = Column(String(200), nullable=False)

    description = Column(Text, nullable=True)

    subject = Column(String(100), nullable=False)

    duration_minutes = Column(Integer, nullable=False)

    start_time = Column(
        DateTime(timezone=True),
        nullable=False
    )

    end_time = Column(
        DateTime(timezone=True),
        nullable=False
    )

    total_marks = Column(Float, nullable=False, default=0.0)

    negative_marking_enabled = Column(
        Boolean,
        default=False,
        nullable=False
    )

    randomize_questions = Column(
        Boolean,
        default=True,
        nullable=False
    )

    # Stores exam configuration such as question counts,
    # difficulty distribution and question type distribution.
    configuration = Column(JSON, nullable=False, default=dict)

    # Stores webcam, gaze sensitivity and tab-warning settings.
    proctor_settings = Column(JSON, nullable=False, default=dict)

    status = Column(
        Enum(
            ExamStatus,
            name="exam_status",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        default=ExamStatus.DRAFT,
        nullable=False
    )

    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    examiner = relationship(
        "User",
        back_populates="created_exams",
        foreign_keys=[examiner_id]
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

    __table_args__ = (
        CheckConstraint(
            "duration_minutes > 0",
            name="check_exam_duration"
        ),
        CheckConstraint(
            "end_time > start_time",
            name="check_exam_schedule"
        ),
    )


# -----------------------------------------
# EXAM QUESTIONS TABLE
# -----------------------------------------

class ExamQuestion(Base):
    __tablename__ = "exam_questions"

    id = Column(Integer, primary_key=True, index=True)

    exam_id = Column(
        Integer,
        ForeignKey("exams.id", ondelete="CASCADE"),
        nullable=False
    )

    question_id = Column(
        Integer,
        ForeignKey("question_bank.id"),
        nullable=False
    )

    question_order = Column(Integer, nullable=False)

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
            "question_id",
            name="unique_exam_question"
        ),
        UniqueConstraint(
            "exam_id",
            "question_order",
            name="unique_exam_question_order"
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

    # Store a hash of the session token, never the raw token.
    session_token_hash = Column(String(255), nullable=True, unique=True)

    started_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    expires_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    submitted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    status = Column(
        Enum(
            SessionStatus,
            name="session_status",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        default=SessionStatus.NOT_STARTED,
        nullable=False
    )

    remaining_seconds = Column(Integer, nullable=True)

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
        UniqueConstraint(
            "exam_id",
            "student_id",
            name="unique_student_exam_session"
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
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    question_id = Column(
        Integer,
        ForeignKey("question_bank.id"),
        nullable=False
    )

    # Text, selected options or uploaded file information.
    answer_text = Column(Text, nullable=True)

    selected_options = Column(JSON, nullable=True)

    uploaded_file_path = Column(String(500), nullable=True)

    word_count = Column(Integer, nullable=True)

    marks_awarded = Column(Float, nullable=True)

    ai_suggested_marks = Column(Float, nullable=True)

    ai_justification = Column(Text, nullable=True)

    matched_points = Column(JSON, nullable=True)

    missed_points = Column(JSON, nullable=True)

    status = Column(
        Enum(
            AnswerStatus,
            name="answer_status",
            values_callable=lambda enum_cls: [
                item.value for item in enum_cls
            ],
        ),
        default=AnswerStatus.NOT_ANSWERED,
        nullable=False
    )

    submitted_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

    session = relationship(
        "ExamSession",
        back_populates="answers"
    )

    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "question_id",
            name="unique_session_question_answer"
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
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False,
        unique=True
    )

    total_marks = Column(Float, nullable=False, default=0.0)

    marks_obtained = Column(Float, nullable=False, default=0.0)

    objective_marks = Column(Float, nullable=False, default=0.0)

    subjective_marks = Column(Float, nullable=False, default=0.0)

    percentage = Column(Float, nullable=False, default=0.0)

    evaluated_at = Column(
        DateTime(timezone=True),
        nullable=True
    )

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
        ForeignKey("exam_sessions.id", ondelete="CASCADE"),
        nullable=False
    )

    event_type = Column(String(100), nullable=False)

    description = Column(Text, nullable=True)

    suspicion_score = Column(Float, nullable=False, default=0.0)

    event_metadata = Column(JSON, nullable=True)

    recorded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    session = relationship(
        "ExamSession",
        back_populates="proctor_events"
    )

    __table_args__ = (
        CheckConstraint(
            "suspicion_score >= 0 AND suspicion_score <= 100",
            name="check_suspicion_score"
        ),
    )
