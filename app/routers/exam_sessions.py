import hmac
import io
from datetime import datetime, timedelta
from math import ceil

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from PIL import Image, ImageOps

from app.auth import (
    EXAM_ACCESS_TOKEN_EXPIRE_MINUTES,
    create_exam_access_token,
    create_exam_refresh_token,
    hash_exam_refresh_token,
    verify_token,
)
from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Exam,
    ExamAssignment,
    ExamQuestion,
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


class ExamTokenRefreshRequest(BaseModel):
    refresh_token: str = Field(
        min_length=32,
        max_length=200,
    )


class QuestionProgressRequest(BaseModel):
    current_question_index: int = Field(ge=0)


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

    if session.status == "not_started":
        prestart_expires_at = normalize_to_naive_utc(session.prestart_expires_at)
        if prestart_expires_at is not None and now >= prestart_expires_at:
            session.status = "expired"
            session.exam_token_refresh_hash = None
            db.commit()
            db.refresh(session)
            return True
        return False

    if session.status != "in_progress":
        return True

    expires_at = normalize_to_naive_utc(session.expires_at)
    if expires_at is None:
        session.status = "expired"
        session.exam_token_refresh_hash = None
        db.commit()
        db.refresh(session)
        return True

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

    token_auth_session_id = payload.get("auth_session_id")
    if student.active_session_id:
        if (
            not isinstance(token_auth_session_id, str)
            or not hmac.compare_digest(
                token_auth_session_id,
                student.active_session_id,
            )
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=(
                    "This examination was signed out because your account "
                    "was used to sign in on another device. Your saved answers "
                    "are preserved. Please sign in again to continue."
                ),
                headers={"WWW-Authenticate": "Bearer"},
            )
    elif token_auth_session_id is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This examination login session is no longer active.",
            headers={"WWW-Authenticate": "Bearer"},
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

    assignment = db.query(ExamAssignment.id).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.student_id == student_id,
        ExamAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your access to this examination has been revoked.",
        )

    return payload, session




def _start_exam_clock(session: ExamSession, exam: Exam, start_at: datetime) -> None:
    """Set the official exam clock from a server-controlled start timestamp."""
    expires_at = start_at + timedelta(minutes=exam.duration_minutes)
    exam_end = normalize_to_naive_utc(exam.end_time)
    if exam_end is not None and exam_end < expires_at:
        expires_at = exam_end
    session.started_at = start_at
    session.expires_at = expires_at
    session.status = "in_progress"
    session.prestart_stage = "in_progress"
    session.start_window_expires_at = None


def _advance_prestart_stage(session: ExamSession, exam: Exam, now: datetime) -> bool:
    """Advance persisted entry stages and auto-start when the 17-second window ends."""
    if session.status != "not_started":
        return False
    changed = False
    if session.prestart_stage == "summary" and session.summary_started_at:
        summary_start = normalize_to_naive_utc(session.summary_started_at)
        if now >= summary_start + timedelta(seconds=120):
            session.prestart_stage = "start_window"
            session.start_window_expires_at = summary_start + timedelta(seconds=137)
            changed = True
    if session.prestart_stage == "start_window" and session.start_window_expires_at:
        deadline = normalize_to_naive_utc(session.start_window_expires_at)
        if now >= deadline:
            _start_exam_clock(session, exam, deadline)
            changed = True
    return changed


def _build_exam_summary(session: ExamSession, exam: Exam, db: Session) -> dict:
    selected_ids = session.selected_question_ids or []
    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(selected_ids or [-1]),
    ).all()
    breakdown = {}
    maximum_marks = 0.0
    negative_marks = 0.0
    for question in questions:
        question_type = getattr(question.question_type, "value", question.question_type)
        breakdown[question_type] = breakdown.get(question_type, 0) + 1
        maximum_marks += float(question.marks or 0)
        if exam.negative_marking:
            negative_marks += abs(float(question.negative_marks or 0))
    creator = db.query(User).filter(User.id == exam.created_by).first()
    student = db.query(User).filter(User.id == session.student_id).first()
    settings = exam.selection_rules if isinstance(exam.selection_rules, dict) else {}
    return {
        "exam_title": exam.title,
        "subject": exam.subject,
        "creator_name": creator.full_name if creator else "Unknown",
        "student_name": student.full_name if student else "Unknown",
        "student_email": student.email if student else None,
        "student_department": student.department if student else None,
        "total_questions": len(selected_ids),
        "question_type_breakdown": breakdown,
        "duration_minutes": exam.duration_minutes,
        "maximum_marks": round(maximum_marks, 2),
        "negative_marking_enabled": bool(exam.negative_marking),
        "total_possible_negative_marks": round(negative_marks, 2),
        "instructions": settings.get("instructions") or settings.get("exam_instructions") or [],
    }

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

    # Serialize session creation per examination. The row lock is held
    # until the session transaction commits, so another student cannot
    # select a paper from a stale view of previously assigned papers.
    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).with_for_update().first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    assignment = db.query(ExamAssignment.id).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.student_id == current_user.id,
        ExamAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This examination has not been assigned to your account.",
        )

    now = get_current_utc_time()

    exam_start = normalize_to_naive_utc(
        exam.start_time
    )

    exam_end = normalize_to_naive_utc(
        exam.end_time
    )

    if exam_start is None or exam_end is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This examination has not been scheduled yet.",
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
        ExamSession.status.in_(("not_started", "in_progress")),
    ).order_by(ExamSession.id.desc()).first()

    if session is not None:
        if expire_session_if_needed(session, db, now):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Your previous exam session has expired or been submitted.",
            )
        if session.status == "not_started" and not session.prestart_stage:
            session.prestart_stage = "face_capture"
            session.prestart_expires_at = now + timedelta(minutes=30)
        try:
            get_or_create_session_question_ids(session, exam, db)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error))
    else:
        try:
            selected_ids = generate_session_question_ids(exam, current_user.id, db)
        except ValueError as error:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error))

        session = ExamSession(
            exam_id=exam_id,
            student_id=current_user.id,
            started_at=None,
            expires_at=None,
            status="not_started",
            prestart_stage="face_capture",
            prestart_expires_at=now + timedelta(minutes=30),
            selected_question_ids=selected_ids,
        )
        try:
            db.add(session)
            db.commit()
            db.refresh(session)
        except IntegrityError:
            db.rollback()
            session = db.query(ExamSession).filter(
                ExamSession.exam_id == exam_id,
                ExamSession.student_id == current_user.id,
                ExamSession.status.in_(("not_started", "in_progress")),
            ).order_by(ExamSession.id.desc()).first()
            if session is None or expire_session_if_needed(session, db, get_current_utc_time()):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Could not create an exam session. Please try again.")

    # Rotate the opaque refresh token whenever a session is issued.
    # Only its SHA-256 digest is stored in the database.
    refresh_token = create_exam_refresh_token()
    session.exam_token_refresh_hash = hash_exam_refresh_token(
        refresh_token
    )
    db.commit()
    db.refresh(session)

    exam_token = create_exam_access_token(
        exam_id=exam_id,
        student_id=current_user.id,
        session_id=session.id,
        expires_at=normalize_to_naive_utc(
            session.expires_at or session.prestart_expires_at
        ),
        auth_session_id=current_user.active_session_id,
    )

    current_time = get_current_utc_time()

    return {
        "message": "Examination entry session created.",
        "session_id": session.id,
        "exam_id": exam_id,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": (
            get_remaining_seconds(session, current_time)
            if session.status == "in_progress" else None
        ),
        "prestart_stage": session.prestart_stage,
        "total_questions": len(
            session.selected_question_ids or []
        ),
        "access_token": exam_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
    }


# ==========================================
# ROTATE SHORT-LIVED EXAM ACCESS TOKEN
# ==========================================

@router.post("/refresh/{session_id}")
def refresh_exam_access_token(
    session_id: int,
    submission: ExamTokenRefreshRequest,
    db: Session = Depends(get_db),
):
    """
    Rotate a one-time refresh token and issue a short-lived exam access token.

    The refresh token is session-specific, expires with the exam session,
    and is stored only as a SHA-256 digest.
    """

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).with_for_update().populate_existing().first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )

    student = db.query(User).filter(
        User.id == session.student_id,
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

    assignment = db.query(ExamAssignment.id).filter(
        ExamAssignment.exam_id == session.exam_id,
        ExamAssignment.student_id == session.student_id,
        ExamAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your access to this examination has been revoked.",
        )

    now = get_current_utc_time()

    token_deadline = (
        session.expires_at if session.status == "in_progress"
        else session.prestart_expires_at if session.status == "not_started"
        else None
    )
    if token_deadline is None or now >= normalize_to_naive_utc(token_deadline):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The examination session is no longer active.",
        )

    stored_hash = session.exam_token_refresh_hash
    supplied_hash = hash_exam_refresh_token(submission.refresh_token)

    if (
        not stored_hash
        or not hmac.compare_digest(stored_hash, supplied_hash)
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The exam refresh token is invalid or has already been rotated.",
        )

    next_refresh_token = create_exam_refresh_token()
    session.exam_token_refresh_hash = hash_exam_refresh_token(
        next_refresh_token
    )

    try:
        db.commit()
        db.refresh(session)
    except Exception:
        db.rollback()
        raise

    access_token = create_exam_access_token(
        exam_id=session.exam_id,
        student_id=session.student_id,
        session_id=session.id,
        expires_at=normalize_to_naive_utc(token_deadline),
        auth_session_id=student.active_session_id,
    )

    return {
        "session_id": session.id,
        "access_token": access_token,
        "refresh_token": next_refresh_token,
        "token_type": "bearer",
        "expires_in_seconds": min(
            EXAM_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            max(
                0,
                int(
                    (
                        normalize_to_naive_utc(token_deadline) - now
                    ).total_seconds()
                ),
            ),
        ),
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
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    if exam and _advance_prestart_stage(session, exam, now):
        db.commit()
        db.refresh(session)

    if session.status == "not_started":
        if expire_session_if_needed(session, db, now):
            return {"session_id": session.id, "status": session.status, "remaining_seconds": 0}
        return {
            "session_id": session.id,
            "status": "not_started",
            "prestart_stage": session.prestart_stage,
            "remaining_seconds": None,
            "is_paused": False,
        }

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
        "is_paused": bool(session.is_paused),
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            now,
        ),
    }


# ==========================================
# PERSIST CURRENT QUESTION PROGRESS
# ==========================================

@router.put("/progress/{session_id}")
def update_exam_question_progress(
    session_id: int,
    data: QuestionProgressRequest,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, validated_session = validate_exam_token(credentials, db)
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.student_id == validated_session.student_id,
    ).with_for_update().first()
    if session is None:
        raise HTTPException(status_code=404, detail="Exam session not found.")
    now = get_current_utc_time()
    if session.status != "in_progress" or expire_session_if_needed(session, db, now):
        raise HTTPException(status_code=409, detail="The examination session is no longer active.")
    if session.is_paused:
        raise HTTPException(status_code=409, detail="Resume the examination before changing question progress.")
    selected_ids = session.selected_question_ids or []
    if data.current_question_index >= len(selected_ids):
        raise HTTPException(status_code=400, detail="Question progress is outside the saved examination paper.")
    session.current_question_index = data.current_question_index
    db.commit()
    return {
        "session_id": session.id,
        "current_question_index": session.current_question_index,
        "saved": True,
    }


# ==========================================
# PAUSE AND RESUME EXAM SESSION
# ==========================================

@router.post("/pause/{session_id}")
def pause_exam_session(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, validated_session = validate_exam_token(credentials, db)
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.student_id == validated_session.student_id,
    ).with_for_update().first()
    if session is None:
        raise HTTPException(status_code=404, detail="Exam session not found.")
    now = get_current_utc_time()
    if session.status != "in_progress" or expire_session_if_needed(session, db, now):
        raise HTTPException(status_code=409, detail="The exam session is no longer active.")
    if not session.is_paused:
        session.is_paused = True
        session.paused_at = now
        db.commit()
    return {
        "session_id": session.id,
        "is_paused": True,
        "remaining_seconds": get_remaining_seconds(session, now),
        "message": "Exam paused. The official exam deadline continues to run.",
    }


@router.post("/resume/{session_id}")
def resume_exam_session(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, validated_session = validate_exam_token(credentials, db)
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.student_id == validated_session.student_id,
    ).with_for_update().first()
    if session is None:
        raise HTTPException(status_code=404, detail="Exam session not found.")
    now = get_current_utc_time()
    if session.status != "in_progress" or expire_session_if_needed(session, db, now):
        raise HTTPException(status_code=409, detail="The exam session is no longer active.")
    session.is_paused = False
    session.paused_at = None
    db.commit()
    return {
        "session_id": session.id,
        "is_paused": False,
        "remaining_seconds": get_remaining_seconds(session, now),
        "message": "Exam resumed.",
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

    if session.status in {"submitted", "auto_submitted"}:
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

    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    if _advance_prestart_stage(session, exam, now):
        db.commit()
        db.refresh(session)

    if expire_session_if_needed(session, db, now):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam session is no longer active.",
        )

    if session.status == "not_started":
        elapsed = 0
        if session.summary_started_at:
            elapsed = max(0, int((now - normalize_to_naive_utc(session.summary_started_at)).total_seconds()))
        selected_ids = session.selected_question_ids or []
        return {
            "exam_id": exam_id,
            "exam_title": exam.title,
            "duration_minutes": exam.duration_minutes,
            "session_id": session.id,
            "started_at": None,
            "expires_at": None,
            "remaining_seconds": None,
            "status": "not_started",
            "prestart_stage": session.prestart_stage or "face_capture",
            "face_captured": bool(session.face_capture_data),
            "face_captured_at": session.face_captured_at,
            "summary_started_at": session.summary_started_at,
            "summary_elapsed_seconds": elapsed,
            "summary_seconds_until_continue": max(0, 60 - elapsed),
            "summary_seconds_until_auto_continue": max(0, 120 - elapsed),
            "start_window_expires_at": session.start_window_expires_at,
            "start_window_seconds_remaining": (
                max(0, ceil((normalize_to_naive_utc(session.start_window_expires_at) - now).total_seconds()))
                if session.start_window_expires_at else None
            ),
            "exam_summary": _build_exam_summary(session, exam, db),
            "total_questions": len(selected_ids),
            "proctoring_enabled": bool(exam.proctoring_enabled),
            "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
            "max_tab_switch_warnings": exam.max_tab_switch_warnings,
            "questions": [],
        }

    if expire_session_if_needed(session, db, now):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam session is no longer active.",
        )

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

        exam_question = db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == exam_id,
            ExamQuestion.question_id == question_id,
        ).first()

        paper.append({
            "id": question.id,
            "question_id": question.id,
            "question_text": question.question_text,
            "question_type": getattr(
                question.question_type,
                "value",
                question.question_type,
            ),
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "question_time_limit_seconds": (
                exam_question.question_time_limit_seconds
                if exam_question else None
            ),
            "question_image_available": bool(question.question_image_path),
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
        "exam_title": exam.title,
        "subject": exam.subject,
        "duration_minutes": exam.duration_minutes,
        "session_id": session.id,
        "status": session.status,
        "prestart_stage": session.prestart_stage,
        "face_captured": bool(session.face_capture_data),
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(
            session,
            get_current_utc_time(),
        ),
        "is_paused": bool(session.is_paused),
        "current_question_index": int(session.current_question_index or 0),
        "total_questions": len(paper),
        "proctoring_enabled": bool(exam.proctoring_enabled),
        "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
        "max_tab_switch_warnings": exam.max_tab_switch_warnings,
        "questions": paper,
}
    




@router.get("/prestart/{session_id}")
def get_prestart_status(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, session = validate_exam_token(credentials, db)
    if session.id != session_id:
        raise HTTPException(status_code=403, detail="Token does not belong to this examination session.")
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    now = get_current_utc_time()
    changed = _advance_prestart_stage(session, exam, now)
    if changed:
        db.commit()
        db.refresh(session)
    if expire_session_if_needed(session, db, now):
        raise HTTPException(status_code=409, detail="The examination entry session has expired.")
    elapsed = 0
    if session.summary_started_at:
        elapsed = max(0, int((now - normalize_to_naive_utc(session.summary_started_at)).total_seconds()))
    return {
        "session_id": session.id,
        "status": session.status,
        "stage": session.prestart_stage,
        "face_captured": bool(session.face_capture_data),
        "summary_elapsed_seconds": elapsed,
        "summary_seconds_until_continue": max(0, 60 - elapsed),
        "summary_seconds_until_auto_continue": max(0, 120 - elapsed),
        "start_window_seconds_remaining": (
            max(0, ceil((normalize_to_naive_utc(session.start_window_expires_at) - now).total_seconds()))
            if session.start_window_expires_at else None
        ),
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(session, now) if session.status == "in_progress" else None,
    }


@router.post("/face-capture/{session_id}")
async def save_face_capture(
    session_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, session = validate_exam_token(credentials, db)
    if session.id != session_id:
        raise HTTPException(status_code=403, detail="Token does not belong to this examination session.")
    if session.status != "not_started" or session.prestart_stage != "face_capture":
        raise HTTPException(status_code=409, detail="Face capture is not available at this stage.")
    content_type = request.headers.get("content-type", "").split(";")[0].strip().lower()
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(status_code=415, detail="Upload the face capture as a JPEG, PNG, or WebP image.")
    image_bytes = await request.body()
    if not image_bytes or len(image_bytes) > 2 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="The face capture must be smaller than 2 MB.")
    try:
        with Image.open(io.BytesIO(image_bytes)) as source:
            source = ImageOps.exif_transpose(source).convert("RGB")
            source.thumbnail((640, 480))
            output = io.BytesIO()
            source.save(output, format="JPEG", quality=82, optimize=True)
            stored_image = output.getvalue()
    except Exception:
        raise HTTPException(status_code=400, detail="The uploaded face capture is not a valid image.")
    now = get_current_utc_time()
    session.face_capture_data = stored_image
    session.face_capture_mime_type = "image/jpeg"
    session.face_captured_at = now
    session.prestart_stage = "summary"
    session.summary_started_at = now
    if session.prestart_expires_at is None:
        session.prestart_expires_at = now + timedelta(minutes=30)
    db.commit()
    return {
        "session_id": session.id,
        "stage": "summary",
        "face_captured": True,
        "summary_started_at": session.summary_started_at,
        "message": "Face capture saved. The examination summary has started.",
    }


@router.post("/summary/continue/{session_id}")
def continue_after_exam_summary(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, session = validate_exam_token(credentials, db)
    if session.id != session_id:
        raise HTTPException(status_code=403, detail="Token does not belong to this examination session.")
    if session.status != "not_started" or session.prestart_stage != "summary" or not session.summary_started_at:
        raise HTTPException(status_code=409, detail="The examination summary is not ready to continue.")
    now = get_current_utc_time()
    summary_start = normalize_to_naive_utc(session.summary_started_at)
    elapsed = (now - summary_start).total_seconds()
    if elapsed < 60:
        raise HTTPException(status_code=409, detail="The examination summary must be displayed for at least 60 seconds.")
    if elapsed >= 120:
        session.start_window_expires_at = summary_start + timedelta(seconds=137)
    else:
        session.start_window_expires_at = now + timedelta(seconds=17)
    session.prestart_stage = "start_window"
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    if exam:
        _advance_prestart_stage(session, exam, now)
    db.commit()
    return {
        "session_id": session.id,
        "stage": session.prestart_stage,
        "start_window_expires_at": session.start_window_expires_at,
        "start_window_seconds_remaining": max(0, ceil((normalize_to_naive_utc(session.start_window_expires_at) - now).total_seconds())) if session.status == "not_started" else 0,
        "status": session.status,
    }


@router.post("/confirm-start/{session_id}")
def confirm_exam_start(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, session = validate_exam_token(credentials, db)
    if session.id != session_id:
        raise HTTPException(status_code=403, detail="Token does not belong to this examination session.")
    exam = db.query(Exam).filter(Exam.id == session.exam_id).with_for_update().first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    now = get_current_utc_time()
    _advance_prestart_stage(session, exam, now)
    if session.status == "not_started":
        if session.prestart_stage != "start_window" or not session.start_window_expires_at:
            raise HTTPException(status_code=409, detail="The examination is not ready to start.")
        if now >= normalize_to_naive_utc(session.start_window_expires_at):
            _advance_prestart_stage(session, exam, now)
        else:
            _start_exam_clock(session, exam, now)
    db.commit()
    db.refresh(session)
    if session.status != "in_progress":
        raise HTTPException(status_code=409, detail="The examination could not be started.")
    return {
        "session_id": session.id,
        "status": session.status,
        "started_at": session.started_at,
        "expires_at": session.expires_at,
        "remaining_seconds": get_remaining_seconds(session, now),
        "message": "Examination started.",
    }

# Resolve the paper from the authenticated session rather than browser-stored exam metadata.
# This also supports safe page reloads when sessionStorage's exam ID is missing.
@router.get("/paper/session/{session_id}")
def get_exam_paper_by_session(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    _, session = validate_exam_token(credentials, db)
    if session.id != session_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Token does not belong to this examination session.",
        )
    return get_exam_paper(
        exam_id=session.exam_id,
        credentials=credentials,
        db=db,
    )
