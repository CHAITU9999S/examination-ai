
from datetime import timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam
from app.schemas import ExamCreate, UserRole
from app.dependencies import require_role
from app.services.exam_config import (
    validate_exam_config,
    normalize_to_naive_utc,
)


router = APIRouter(
    prefix="/exams",
    tags=["Exam Configuration"]
)


# ==========================================
# CREATE EXAM
# ==========================================

@router.post("/", status_code=status.HTTP_201_CREATED)
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
            data.max_tab_switch_warnings,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    exam = Exam(
        title=data.title,
        subject=data.subject,
        duration_minutes=data.duration_minutes,
        total_questions=data.total_questions,
        randomize_questions=data.randomize_questions,
        selection_rules=data.selection_rules,

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
        created_by=current_user.id,
    )

    try:
        db.add(exam)
        db.commit()
        db.refresh(exam)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam could not be created because of a database constraint."
        )

    return {
        "message": "Exam created successfully",
        "exam_id": exam.id,
    }


# ==========================================
# LIST EXAMS
# ==========================================

@router.get("/")
def list_exams(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("student", "examiner", "admin")
    )
):
    query = db.query(Exam)

    # Students can discover available examinations.
    # Examiners can access only their own exams.
    # Admins can view all exams.
    if current_user.role == UserRole.EXAMINER.value:
        query = query.filter(
            Exam.created_by == current_user.id
        )

    exams = query.order_by(
        Exam.id.desc()
    ).all()

    def utc_timestamp(value):
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    return [
        {
            "id": exam.id,
            "title": exam.title,
            "subject": exam.subject,
            "duration_minutes": exam.duration_minutes,
            "total_questions": exam.total_questions,
            "randomize_questions": exam.randomize_questions,
            "selection_rules": exam.selection_rules,
            "start_time": utc_timestamp(exam.start_time),
            "end_time": utc_timestamp(exam.end_time),
            "negative_marking": exam.negative_marking,
            "proctoring_enabled": exam.proctoring_enabled,
            "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
            "max_tab_switch_warnings": exam.max_tab_switch_warnings,
            "created_by": exam.created_by,
        }
        for exam in exams
    ]
    
