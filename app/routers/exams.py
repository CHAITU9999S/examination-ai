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
    if data.start_time and data.end_time:
        if data.end_time <= data.start_time:
            raise HTTPException(
                status_code=400,
                detail="End time must be after start time"
            )

    exam = Exam(
        title=data.title,
        subject=data.subject,
        duration_minutes=data.duration_minutes,
        start_time=data.start_time,
        end_time=data.end_time,
        negative_marking=data.negative_marking,
        proctoring_enabled=data.proctoring_enabled,
        created_by=current_user.id
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
