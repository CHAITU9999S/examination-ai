from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Exam, ExamSession
from app.auth import create_exam_access_token

router = APIRouter(
    prefix="/exam-sessions",
    tags=["Exam Sessions"]
)


@router.post("/start/{exam_id}")
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user.role != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can start exams"
        )

    exam = db.query(Exam).filter(Exam.id == exam_id).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    now = datetime.utcnow()

    if exam.start_time and now < exam.start_time:
        raise HTTPException(
            status_code=400,
            detail="Exam has not started yet"
        )

    if exam.end_time and now > exam.end_time:
        raise HTTPException(
            status_code=400,
            detail="Exam schedule has ended"
        )

    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == current_user.id,
        ExamSession.status == "in_progress"
    ).first()

    if not session:
        session = ExamSession(
            exam_id=exam_id,
            student_id=current_user.id
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    exam_token = create_exam_access_token(
        exam_id=exam_id,
        student_id=current_user.id
    )

    return {
        "message": "Exam session started",
        "session_id": session.id,
        "exam_id": exam_id,
        "access_token": exam_token,
        "token_type": "bearer"
          }
