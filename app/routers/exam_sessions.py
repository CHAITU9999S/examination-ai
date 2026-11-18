from datetime import datetime, timedelta
from math import ceil

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    create_exam_access_token,
    verify_token,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Exam,
    ExamSession,
    Option,
    QuestionBank,
    User,
)
from app.services.exam_config import normalize_to_naive_utc
from app.services.session_service import (
    generate_session_question_ids,
    get_or_create_session_question_ids,
)
from app.services.evaluation_service import evaluate_exam_session


router = APIRouter(
    prefix="/exam-sessions",
    tags=["Exam Sessions"],
)

exam_token_scheme = HTTPBearer(auto_error=False)


# ==========================================
# TIME HELPERS
# ==========================================

def get_current_utc_time() -> datetime:
    """Return current UTC time as a naive UTC datetime."""
    return datetime.utcnow()


def get_remaining_seconds(
    session: ExamSession,
    now: datetime,
) -> int:
    remaining = (
        normalize_to_naive_utc(session.expires_at) - now
    ).total_seconds()

    return max(0, ceil(remaining))


def expire_session_if_needed(
    session: ExamSession,
    db: Session,
    now: datetime,
) -> bool:
    """Mark an active session submitted when its time expires."""

    if session.status != "in_progress":
        return True

    expires_at = normalize_to_naive_utc(
        session.expires_at
    )

    if now >= expires_at:
        session.status = "submitted"
        session.submitted_at = now
        db.commit()
        db.refresh(session)

        try:
            evaluate_exam_session(
                db,
                session.id,
            )
        except Exception as error:
            # Submission must remain committed even if grading needs
            # examiner intervention because of a question configuration issue.
            print(
                "Automatic evaluation could not be completed:",
                str(error),
            )

        return True

    return False


# ==========================================
# EXAM TOKEN VALIDATION
# ==========================================

def validate_exam_token(
    credentials: HTTPAuthorizationCredentials,
    db: Session,
):
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Exam authentication is required.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(
        credentials.credentials,
        expected_token_type="exam",
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired exam token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        exam_id = int(payload["exam_id"])
        student_id = int(payload["student_id"])
        token_user_id = int(payload["sub"])
        session_id = int(payload["session_id"])

    except (KeyError, TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Exam token identity is invalid.",
        )

    if student_id != token_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Exam token identity mismatch.",
        )

    student = db.query(User).filter(
        User.id == student_id
    ).first()

    if (
        student is None
        or not student.is_active
        or student.role != "student"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student account is invalid or inactive.",
        )

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == student_id,
    ).first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam session not found.",
        )

    return payload, session


# ==========================================
# START EXAM
# ==========================================

@router.post("/start/{exam_id}")
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can start examinations.",
        )

    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    now = get_current_utc_time()

    exam_start = normalize_to_naive_utc(
        exam.start_time
    )

    exam_end = normalize_to_naive_utc(
        exam.end_time
    )

    if exam_start and now < exam_start:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam has not started yet.",
        )

    if exam_end and now >= exam_end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam schedule has ended.",
        )

    if not exam.duration_minutes or exam.duration_minutes <= 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Exam duration is not configured correctly.",
        )

    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == current_user.id,
        ExamSession.status == "in_progress",
    ).first()

    if session is not None:
        if expire_session_if_needed(session, db, now):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Your previous exam session has expired or been submitted.",
            )

        try:
            get_or_create_session_question_ids(
                session,
                exam,
                db,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=str(error),
            )

    else:
        expires_at = now + timedelta(
            minutes=exam.duration_minutes
        )

        if exam_end and exam_end < expires_at:
            expires_at = exam_end

        try:
            selected_ids = generate_session_question_ids(
                exam,
                current_user.id,
                db,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(error),
            )

        session = ExamSession(
            exam_id=exam_id,
            student_id=current_user.id,
            started_at=now,
            expires_at=expires_at,
            status="in_progress",
            selected_question_ids=selected_ids,
        )

        try:
            db.add(session)
            db.commit()
            db.refresh(session)

        except IntegrityError:
            db.rollback()

            # Another simultaneous request may have created
            # the unique active session first.
            session = db.query(ExamSession).filter(
                ExamSession.exam_id == exam_id,
                ExamSession.student_id == current_user.id,
                ExamSession.status == "in_progress",
            ).first()

            if session is None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Could not create an exam session. Please try again.",
                )

            if expire_session_if_needed(
                session,
                db,
                get_current_utc_time(),
            ):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Your exam session has expired or been submitted.",
                )

    exam_token = create_exam_access_token(
        exam_id=exam_id,
        student_id=current_user.id,
        session_id=session.id,
        expires_at=normalize_to_naive_utc(
            session.expires_at
        ),
    )

    current_time = get_current_utc_time()

    return {
        "message": "Exam session started.",
        "session_id": session.id,
        "exam_id": exam_id,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            current_time,
        ),
        "total_questions": len(
            session.selected_question_ids or []
        ),
        "access_token": exam_token,
        "token_type": "bearer",
    }


# ==========================================
# GET REMAINING EXAM TIME
# ==========================================

@router.get("/time/{session_id}")
def get_exam_remaining_time(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db),
):
    payload, session = validate_exam_token(
        credentials,
        db,
    )

    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to this exam session.",
        )

    now = get_current_utc_time()

    if expire_session_if_needed(session, db, now):
        return {
            "session_id": session.id,
            "status": session.status,
            "remaining_seconds": 0,
            "message": "Exam time has expired or the exam has been submitted.",
        }

    return {
        "session_id": session.id,
        "exam_id": session.exam_id,
        "status": session.status,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            now,
        ),
    }


# ==========================================
# SUBMIT EXAM
# ==========================================

@router.post("/submit/{session_id}")
def submit_exam(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db),
):
    payload, session = validate_exam_token(
        credentials,
        db,
    )

    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to this exam session.",
        )

    if session.status == "submitted":
        try:
            evaluation = evaluate_exam_session(
                db,
                session.id,
            )
        except Exception as error:
            evaluation = {
                "status": "pending_manual_review",
                "message": str(error),
            }

        return {
            "message": "Exam has already been submitted.",
            "session_id": session.id,
            "status": session.status,
            "submitted_at": session.submitted_at,
            "evaluation": evaluation,
        }

    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exam session cannot be submitted.",
        )

    now = get_current_utc_time()

    if expire_session_if_needed(session, db, now):
        return {
            "message": "Exam time expired. Exam submitted automatically.",
            "session_id": session.id,
            "status": session.status,
            "submitted_at": session.submitted_at,
        }

    session.status = "submitted"
    session.submitted_at = now

    try:
        db.commit()
        db.refresh(session)

    except Exception:
        db.rollback()
        raise

    try:
        evaluation = evaluate_exam_session(
            db,
            session.id,
        )
    except Exception as error:
        evaluation = {
            "status": "pending_manual_review",
            "message": str(error),
        }

    return {
        "message": "Exam submitted successfully.",
        "evaluation": evaluation,
        "session_id": session.id,
        "exam_id": session.exam_id,
        "status": session.status,
        "submitted_at": session.submitted_at,
        "remaining_seconds": 0,
    }


# ==========================================
# GET EXAM PAPER
# ==========================================

@router.get("/paper/{exam_id}")
def get_exam_paper(
    exam_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db),
):
    payload, session = validate_exam_token(
        credentials,
        db,
    )

    if int(payload["exam_id"]) != exam_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to this exam.",
        )

    now = get_current_utc_time()

    if expire_session_if_needed(session, db, now):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam session is no longer active.",
        )

    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    try:
        selected_ids = get_or_create_session_question_ids(
            session,
            exam,
            db,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    if not selected_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No questions are available for this exam session.",
        )

    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(selected_ids)
    ).all()

    question_map = {
        question.id: question
        for question in questions
    }

    if len(question_map) != len(selected_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more questions in this exam paper are unavailable.",
        )

    paper = []

    # Preserve the exact question order saved in this session.
    for question_id in selected_ids:
        question = question_map[question_id]

        options = db.query(Option).filter(
            Option.question_id == question_id
        ).order_by(
            Option.id
        ).all()

        paper.append({
            "question_id": question.id,
            "question_text": question.question_text,
            "question_type": getattr(
                question.question_type,
                "value",
                question.question_type,
            ),
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "options": [
                {
                    "id": option.id,
                    "option_text": option.option_text,
                }
                for option in options
            ],
        })

    return {
        "exam_id": exam_id,
        "session_id": session.id,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            get_current_utc_time(),
        ),
        "total_questions": len(paper),
        "proctoring_enabled": bool(exam.proctoring_enabled),
        "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
        "max_tab_switch_warnings": exam.max_tab_switch_warnings,
        "questions": paper,
}
    
