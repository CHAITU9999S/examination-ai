from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import (
    AliasChoices,
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    model_validator,
)


# ==========================================
# USER ROLES
# ==========================================

class UserRole(str, Enum):
    STUDENT = "student"
    EXAMINER = "examiner"
    ADMIN = "admin"


# ==========================================
# QUESTION ENUMERATIONS
# ==========================================

class QuestionTypeSchema(str, Enum):
    MCQ = "MCQ"
    MULTI_SELECT = "multi_select"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    IMAGE_UPLOAD = "image_upload"

    @classmethod
    def _missing_(cls, value):
        # Accept older lowercase MCQ requests.
        if isinstance(value, str) and value.lower() == "mcq":
            return cls.MCQ
        return None


class DifficultyLevelSchema(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# ==========================================
# COMMON BASE SCHEMA
# ==========================================

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ==========================================
# STUDENT REGISTRATION
# ==========================================

class StudentRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# ==========================================
# ONE-TIME INITIAL ADMIN BOOTSTRAP
# ==========================================

class InitialAdminBootstrapRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# ==========================================
# LOGIN
# ==========================================

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# ==========================================
# TOKEN RESPONSE
# ==========================================

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# ==========================================
# USER RESPONSE
# ==========================================

class UserResponse(BaseSchema):
    id: int
    full_name: str
    email: EmailStr
    department: str | None = None
    role: UserRole
    is_active: bool | None = True


# ==========================================
# ADMIN USER CREATION
# ==========================================

class AdminUserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    department: str | None = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


# ==========================================
# USER ACCOUNT STATUS
# ==========================================

class UserStatusUpdate(BaseModel):
    is_active: bool


# ==========================================
# PASSWORD CHANGE
# ==========================================

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# ==========================================
# QUESTION CREATION
# ==========================================

class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)

    question_type: QuestionTypeSchema

    subject: str = Field(min_length=1, max_length=100)

    # Retained for compatibility with older API clients.
    # The current database has no separate topic column.
    topic: str | None = Field(default=None, max_length=150)

    difficulty: DifficultyLevelSchema

    options: list[str] | None = None

    expected_answer: str | None = None

    model_answer_text: str | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "model_answer_text",
            "model_answer"
        )
    )

    tags: list[str] | None = Field(
        default=None,
        validation_alias=AliasChoices(
            "tags",
            "keywords"
        )
    )

    marks: float = Field(gt=0, allow_inf_nan=False)

    negative_marks: float = Field(
        default=0.0,
        ge=0,
        allow_inf_nan=False
    )

    correct_option_index: int | None = Field(
        default=None,
        ge=0
    )

    correct_option_indices: list[int] | None = None

    @property
    def model_answer(self):
        return self.model_answer_text

    @property
    def keywords(self):
        return self.tags


# ==========================================
# EXAM CREATION
# ==========================================

class ExamCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)

    subject: str | None = Field(
        default=None,
        max_length=100
    )

    duration_minutes: int = Field(gt=0)

    total_questions: int = Field(gt=0)

    randomize_questions: bool = True

    selection_rules: dict[str, Any] | None = None

    start_time: datetime | None = None

    end_time: datetime | None = None

    negative_marking: bool = False

    proctoring_enabled: bool = False

    gaze_tracking_sensitivity: float = Field(
        default=0.5,
        ge=0,
        le=1,
        allow_inf_nan=False
    )

    max_tab_switch_warnings: int = Field(
        default=3,
        ge=0
    )

    @model_validator(mode="after")
    def check_schedule_times(self):
        if (self.start_time is None) != (self.end_time is None):
            raise ValueError(
                "Enter both examination schedule times, or leave both empty."
            )
        return self


class ExamScheduleUpdate(BaseModel):
    start_time: datetime
    end_time: datetime


# ==========================================
# GENERAL MESSAGE RESPONSE
# ==========================================

class MessageResponse(BaseModel):
    message: str
