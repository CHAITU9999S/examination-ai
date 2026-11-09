from datetime import datetime
from typing import Optional, List, Literal

from pydantic import BaseModel, EmailStr, Field, ConfigDict


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    department: Optional[str] = None
    password: str = Field(min_length=8)
    role: Literal["student", "examiner", "admin"] = "student"


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str

    model_config = ConfigDict(from_attributes=True)


class QuestionCreate(BaseModel):
    question_text: str
    question_type: Literal[
    "MCQ",
    "multi_select",
    "short_answer",
    "long_answer",
    "image_upload"
]

    subject: str
    difficulty: Literal["Easy", "Medium", "Hard"]
    expected_answer: Optional[str] = None
    marks: float = Field(gt=0)
    negative_marks: float = Field(default=0, ge=0)
    tags: List[str] = Field(default_factory=list)
    options: List[str] = Field(default_factory=list)


class ExamCreate(BaseModel):
    title: str
    subject: str
    duration_minutes: int = Field(gt=0)
    total_questions: int = Field(default=0, ge=0)
    randomize_questions: bool = True
    selection_rules: Optional[dict] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    negative_marking: bool = False
    proctoring_enabled: bool = True
class UserLogin(BaseModel):
    email: EmailStr
    password: str
