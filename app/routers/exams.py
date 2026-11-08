from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam
from app.schemas import ExamCreate
from app.dependencies import require_role

router = APIRouter(prefix="/exams", tags=["Exam Configuration"])


@router.post("/")
def create_exam(
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    exam = Exam(
        title=data.title,
        subject=data.subject,
        duration_minutes=data.duration_minutes,
        start_time=datetime.fromisoformat(data.start_time)
        if data.start_time else None,
        end_time=datetime.fromisoformat(data.end_time)
        if data.end_time else None,
        negative_marking=data.negative_marking,
        proctoring_enabled=data.proctoring_enabled,
        created_by=current_user.id
    )

    if (
        exam.start_time and exam.end_time
        and exam.end_time <= exam.start_time
    ):
        raise HTTPException(
            status_code=400,
            detail="End time must be after start time"
        )

    db.add(exam)
    db.commit()
    db.refresh(exam)

    return {
        "message": "Exam created successfully",
        "exam_id": exam.id
    }


@router.get("/")
def list_exams(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    exams = db.query(Exam).all()

    return [
        {
            "id": exam.id,
            "title": exam.title,
            "subject": exam.subject,
            "duration_minutes": exam.duration_minutes,
            "start_time": exam.start_time,
            "end_time": exam.end_time,
            "negative_marking": exam.negative_marking,
            "proctoring_enabled": exam.proctoring_enabled
        }
        for exam in exams
]
