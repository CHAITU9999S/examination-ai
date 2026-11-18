
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam
from app.schemas import ExamCreate
from app.dependencies import require_role
from app.services.exam_config import (
    validate_exam_config,
    normalize_to_naive_utc
)

router = APIRouter(
    prefix="/exams",
    tags=["Exam Configuration"]
)


@router.post("/")
def create_exam(
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("examiner", "admin")
    )
):
    try:
        validate_exam_config(
            data.duration_minutes,
            data.start_time,
            data.end_time,
            data.selection_rules,
            data.total_questions,
            data.gaze_tracking_sensitivity,
            data.max_tab_switch_warnings
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    exam = Exam(
        title=data.title,
        subject=data.subject,
        duration_minutes=data.duration_minutes,
        total_questions=data.total_questions,
        randomize_questions=data.randomize_questions,
        selection_rules=data.selection_rules,

        # Store schedule timestamps as naive UTC.
        start_time=normalize_to_naive_utc(
            data.start_time
        ),
        end_time=normalize_to_naive_utc(
            data.end_time
        ),

        negative_marking=data.negative_marking,
        proctoring_enabled=data.proctoring_enabled,
        gaze_tracking_sensitivity=data.gaze_tracking_sensitivity,
        max_tab_switch_warnings=data.max_tab_switch_warnings,
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
    current_user=Depends(
        require_role("examiner", "admin")
    )
):
    exams = db.query(Exam).all()

    return [
        {
            "id": exam.id,
            "title": exam.title,
            "subject": exam.subject,
            "duration_minutes": exam.duration_minutes,
            "total_questions": exam.total_questions,
            "randomize_questions": exam.randomize_questions,
            "selection_rules": exam.selection_rules,

            # Return timestamps with an explicit UTC offset.
            "start_time": (
                exam.start_time.replace(tzinfo=timezone.utc)
                if exam.start_time else None
            ),
            "end_time": (
                exam.end_time.replace(tzinfo=timezone.utc)
                if exam.end_time else None
            ),

            "negative_marking": exam.negative_marking,
            "proctoring_enabled": exam.proctoring_enabled,
            "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
            "max_tab_switch_warnings": exam.max_tab_switch_warnings
        }
        for exam in exams
]
    
