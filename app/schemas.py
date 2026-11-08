from pydantic import BaseModel, EmailStr, Field
from typing import Optional, List


class UserCreate(BaseModel):
    full_name: str
    email: EmailStr
    department: Optional[str] = None
    password: str
    role: str = "student"


class UserResponse(BaseModel):
    id: int
    full_name: str
    email: EmailStr
    role: str

    class Config:
        from_attributes = True


class QuestionCreate(BaseModel):
    question_text: str
    question_type: str
    subject: str
    difficulty: str
    expected_answer: Optional[str] = None
    marks: float = Field(gt=0)
    negative_marks: float = Field(default=0, ge=0)
    tags: List[str] = []
    options: List[str] = []


class ExamCreate(BaseModel):
    title: str
    subject: str
    duration_minutes: int = Field(gt=0)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    negative_marking: bool = False
    proctoring_enabled: bool = True
