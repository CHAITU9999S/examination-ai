
from datetime import datetime, timedelta
from math import ceil

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Exam, ExamSession, QuestionBank, Option, User
from app.auth import create_exam_access_token, verify_token
from app.services.session_paper import (
    generate_session_question_ids,
    get_or_create_session_question_ids
)
from app.services.exam_config import normalize_to_naive_utc


exam_token_scheme = HTTPBearer()

router = APIRouter(
    prefix="/exam-sessions",
    tags=["Exam Sessions"]
)


def expire_session_if_needed(
    session: ExamSession,
    db: Session,
    now: datetime
) -> bool:

    if session.status != "in_progress":
        return True

    if now >= session.expires_at:
        session.status = "submitted"
        session.submitted_at = now
        db.commit()
        db.refresh(session)
        return True

    return False


def get_remaining_seconds(
    session: ExamSession,
    now: datetime
) -> int:

    remaining = (
        session.expires_at - now
    ).total_seconds()

    return max(0, ceil(remaining))


def validate_exam_token(
    credentials: HTTPAuthorizationCredentials,
    db: Session
):
    payload = verify_token(credentials.credentials)

    if not payload or payload.get("token_type") != "exam":
        raise HTTPException(
            status_code=401,
            detail="Invalid exam token"
        )

    try:
        exam_id = int(payload.get("exam_id"))
        student_id = int(payload.get("student_id"))
        token_user_id = int(payload.get("sub"))
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid exam token identity"
        )

    if student_id != token_user_id:
        raise HTTPException(
            status_code=401,
            detail="Exam token identity mismatch"
        )

    student = db.query(User).filter(
        User.id == student_id
    ).first()

    if (
        not student
        or not student.is_active
        or student.role != "student"
    ):
        raise HTTPException(
            status_code=403,
            detail="Student account is invalid or inactive"
        )

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == student_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=403,
            detail="Exam session not found"
        )

    return payload, session


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

    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    now = datetime.utcnow()

    # Normalize stored exam schedule timestamps to naive UTC.
    exam_start = normalize_to_naive_utc(
        exam.start_time
    )

    exam_end = normalize_to_naive_utc(
        exam.end_time
    )

    if exam_start and now < exam_start:
        raise HTTPException(
            status_code=400,
            detail="Exam has not started yet"
        )

    if exam_end and now >= exam_end:
        raise HTTPException(
            status_code=400,
            detail="Exam schedule has ended"
        )

    if not exam.duration_minutes or exam.duration_minutes <= 0:
        raise HTTPException(
            status_code=400,
            detail="Exam duration is not configured correctly"
        )

    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == current_user.id,
        ExamSession.status == "in_progress"
    ).first()

    if session:

        if expire_session_if_needed(session, db, now):
            raise HTTPException(
                status_code=400,
                detail="Your previous exam session has expired or been submitted"
            )

        try:
            get_or_create_session_question_ids(
                session,
                exam,
                db
            )
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            )

    else:

        expires_at = now + timedelta(
            minutes=exam.duration_minutes
        )

        # The exam cannot continue beyond its closing time.
        if exam_end and exam_end < expires_at:
            expires_at = exam_end

        try:
            selected_ids = generate_session_question_ids(
                exam,
                current_user.id,
                db
            )
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=str(error)
            )

        session = ExamSession(
            exam_id=exam_id,
            student_id=current_user.id,
            started_at=now,
            expires_at=expires_at,
            status="in_progress",
            selected_question_ids=selected_ids
        )

        db.add(session)

        try:
            db.commit()
            db.refresh(session)

        except IntegrityError:
            db.rollback()

            session = db.query(ExamSession).filter(
                ExamSession.exam_id == exam_id,
                ExamSession.student_id == current_user.id,
                ExamSession.status == "in_progress"
            ).first()

            if not session:
                raise HTTPException(
                    status_code=409,
                    detail="Could not create an exam session. Please try again"
                )

            if expire_session_if_needed(
                session,
                db,
                datetime.utcnow()
            ):
                raise HTTPException(
                    status_code=400,
                    detail="Your exam session has expired or been submitted"
                )

            try:
                get_or_create_session_question_ids(
                    session,
                    exam,
                    db
                )
            except ValueError as error:
                raise HTTPException(
                    status_code=400,
                    detail=str(error)
                )

    exam_token = create_exam_access_token(
        exam_id=exam_id,
        student_id=current_user.id,
        session_id=session.id,
        expires_at=session.expires_at
    )

    current_time = datetime.utcnow()

    return {
        "message": "Exam session started",
        "session_id": session.id,
        "exam_id": exam_id,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            current_time
        ),
        "total_questions": len(session.selected_question_ids or []),
        "access_token": exam_token,
        "token_type": "bearer"
    }


@router.get("/time/{session_id}")
def get_exam_remaining_time(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db)
):

    payload, session = validate_exam_token(
        credentials,
        db
    )

    if session.id != session_id:
        raise HTTPException(
            status_code=403,
            detail="Token does not belong to this exam session"
        )

    now = datetime.utcnow()

    if expire_session_if_needed(session, db, now):
        return {
            "session_id": session.id,
            "status": "submitted",
            "remaining_seconds": 0,
            "message": "Exam time has expired or the exam has been submitted"
        }

    return {
        "session_id": session.id,
        "exam_id": session.exam_id,
        "status": session.status,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            now
        )
    }


@router.post("/submit/{session_id}")
def submit_exam(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db)
):

    payload, session = validate_exam_token(
        credentials,
        db
    )

    if session.id != session_id:
        raise HTTPException(
            status_code=403,
            detail="Token does not belong to this exam session"
        )

    if session.status == "submitted":
        return {
            "message": "Exam has already been submitted",
            "session_id": session.id,
            "status": session.status,
            "submitted_at": session.submitted_at
        }

    if session.status != "in_progress":
        raise HTTPException(
            status_code=409,
            detail="This exam session cannot be submitted"
        )

    now = datetime.utcnow()

    if now >= session.expires_at:
        expire_session_if_needed(
            session,
            db,
            now
        )

        return {
            "message": "Exam time expired. Exam submitted automatically",
            "session_id": session.id,
            "status": session.status,
            "submitted_at": session.submitted_at
        }

    session.status = "submitted"
    session.submitted_at = now

    db.commit()
    db.refresh(session)

    return {
        "message": "Exam submitted successfully",
        "session_id": session.id,
        "exam_id": session.exam_id,
        "status": session.status,
        "submitted_at": session.submitted_at,
        "remaining_seconds": 0
    }


@router.get("/paper/{exam_id}")
def get_exam_paper(
    exam_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db)
):

    payload, session = validate_exam_token(
        credentials,
        db
    )

    token_exam_id = int(payload["exam_id"])

    if token_exam_id != exam_id:
        raise HTTPException(
            status_code=403,
            detail="Token does not belong to this exam"
        )

    now = datetime.utcnow()

    if session.status != "in_progress":
        raise HTTPException(
            status_code=403,
            detail="Exam session is no longer active"
        )

    if expire_session_if_needed(session, db, now):
        raise HTTPException(
            status_code=403,
            detail="Exam time has expired"
        )

    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    try:
        selected_ids = get_or_create_session_question_ids(
            session,
            exam,
            db
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error)
        )

    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(selected_ids)
    ).all()

    question_map = {
        question.id: question
        for question in questions
    }

    missing_ids = [
        question_id
        for question_id in selected_ids
        if question_id not in question_map
    ]

    if missing_ids:
        raise HTTPException(
            status_code=409,
            detail="One or more questions in this exam paper are no longer available"
        )

    paper = []

    # Use the saved ID order, not the database query order.
    for question_id in selected_ids:

        question = question_map[question_id]

        options = db.query(Option).filter(
            Option.question_id == question_id
        ).order_by(Option.id).all()

        paper.append({
            "question_id": question.id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "options": [
                {
                    "id": option.id,
                    "option_text": option.option_text
                }
                for option in options
            ]
        })

    return {
        "exam_id": exam_id,
        "session_id": session.id,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            datetime.utcnow()
        ),
        "total_questions": len(paper),
        "questions": paper
}
    
