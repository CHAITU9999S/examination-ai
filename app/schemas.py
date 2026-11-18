
from enum import Enum
from typing import Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
)


# -----------------------------------------
# USER ROLES
# -----------------------------------------

class UserRole(str, Enum):
    STUDENT = "student"
    EXAMINER = "examiner"
    ADMIN = "admin"


# -----------------------------------------
# QUESTION ENUMERATIONS
# -----------------------------------------

class QuestionTypeSchema(str, Enum):
    MCQ = "mcq"
    MULTI_SELECT = "multi_select"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    IMAGE_UPLOAD = "image_upload"


class DifficultyLevelSchema(str, Enum):
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


# -----------------------------------------
# COMMON BASE SCHEMA
# -----------------------------------------

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------
# STUDENT REGISTRATION
# -----------------------------------------

class StudentRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# -----------------------------------------
# LOGIN
# -----------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# -----------------------------------------
# TOKEN RESPONSE
# -----------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# -----------------------------------------
# USER RESPONSE
# -----------------------------------------

class UserResponse(BaseSchema):
    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool


# -----------------------------------------
# ADMIN USER CREATION
# -----------------------------------------

class AdminUserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


# -----------------------------------------
# USER ACCOUNT STATUS
# -----------------------------------------

class UserStatusUpdate(BaseModel):
    is_active: bool


# -----------------------------------------
# PASSWORD CHANGE
# -----------------------------------------

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# -----------------------------------------
# QUESTION CREATION
# -----------------------------------------

class QuestionCreate(BaseModel):
    question_text: str = Field(min_length=1)
    question_type: QuestionTypeSchema

    subject: str = Field(min_length=1, max_length=100)
    topic: Optional[str] = Field(default=None, max_length=150)

    difficulty: DifficultyLevelSchema

    options: Optional[list[str]] = None

    expected_answer: Optional[str] = None
    model_answer: Optional[str] = None

    keywords: Optional[list[str]] = None

    marks: float = Field(gt=0)
    negative_marks: float = Field(default=0.0, ge=0)

    correct_option_index: Optional[int] = Field(default=None, ge=0)
    correct_option_indices: Optional[list[int]] = None


# -----------------------------------------
# GENERAL MESSAGE RESPONSE
# -----------------------------------------

class MessageResponse(BaseModel):
    message: str
    
