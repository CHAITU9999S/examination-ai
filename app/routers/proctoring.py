
import json
from datetime import datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.database import get_db
from app.models import (
    Exam,
    ExamSession,
    ProctorEvent,
    User,
)
from app.services.proctoring_service import get_proctoring_summary


router = APIRouter(
    prefix="/exam-sessions",
    tags=["AI Proctoring"],
)

exam_token_scheme = HTTPBearer(auto_error=False)
user_token_scheme = HTTPBearer(auto_error=False)


# ==========================================
# PROCTORING EVENT CONFIGURATION
# ==========================================

EVENT_SUSPICION_POINTS = {
    "tab_switch": 10,
    "window_blur": 5,
    "window_focus": 0,
    "face_not_detected": 5,
    "multiple_faces": 20,
    "gaze_away": 3,
    "webcam_error": 2,
    "heartbeat": 0,
}

MAX_SNAPSHOT_LENGTH = 100000


# ==========================================
# REQUEST SCHEMA
# ==========================================

class ProctorEventSubmission(BaseModel):
    event_type: str = Field(
        min_length=1,
        max_length=100,
    )

    description: str | None = Field(
        default=None,
        max_length=1000,
    )

    gaze_data: dict[str, Any] | None = None

    snapshot_data: str | None = Field(
        default=None,
        max_length=MAX_SNAPSHOT_LENGTH,
    )


# ==========================================
# TIME HELPER
# ==========================================

def get_current_utc_time() -> datetime:
    """Return current UTC time without timezone information."""

    return datetime.utcnow()


# ==========================================
# EXAM TOKEN VALIDATION
# ==========================================

def validate_proctoring_token(
    token: str,
    session_id: int,
    db: Session,
):
    """Validate exam token and verify student/session ownership."""

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Exam access token is required.",
        )

    payload = verify_token(
        token,
        expected_token_type="exam",
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired exam access token.",
        )

    try:
        exam_id = int(payload.get("exam_id"))
        student_id = int(payload.get("student_id"))
        token_user_id = int(payload.get("sub"))
        token_session_id = int(payload.get("session_id"))

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid exam token identity.",
        )

    if (
        student_id != token_user_id
        or token_session_id != session_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam token identity mismatch.",
        )

    student = db.query(User).filter(
        User.id == student_id,
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
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )

    return session


# ==========================================
# ACTIVE SESSION VALIDATION
# ==========================================

def validate_active_proctoring_session(
    session: ExamSession,
):
    """Ensure the exam session is still active and not expired."""

    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Proctoring is unavailable for an inactive exam session.",
        )

    now = get_current_utc_time()

    if (
        session.expires_at is None
        or now >= session.expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The examination session has expired.",
        )

    return session


# ==========================================
# RECORD PROCTORING EVENT
# ==========================================

@router.post(
    "/{session_id}/proctoring/events",
    status_code=status.HTTP_201_CREATED,
)
def record_proctoring_event(
    session_id: int,
    submission: ProctorEventSubmission,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db),
):
    """Record a proctoring event for the authenticated exam session."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Exam access token is required.",
        )

    session = validate_proctoring_token(
        token=credentials.credentials,
        session_id=session_id,
        db=db,
    )

    validate_active_proctoring_session(session)

    exam = db.query(Exam).filter(
        Exam.id == session.exam_id,
    ).first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination not found.",
        )

    if not exam.proctoring_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Proctoring is not enabled for this examination.",
        )

    event_type = submission.event_type.strip().lower()

    if event_type not in EVENT_SUSPICION_POINTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported proctoring event type.",
        )

    if (
        submission.snapshot_data is not None
        and len(submission.snapshot_data) > MAX_SNAPSHOT_LENGTH
    ):
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Proctoring snapshot is too large.",
        )

    suspicion_points = EVENT_SUSPICION_POINTS[event_type]

    description = (
        submission.description.strip()
        if submission.description
        else event_type.replace("_", " ").capitalize()
    )

    if not description:
        description = event_type.replace("_", " ").capitalize()

    try:
        tab_switch_count = None

        if event_type == "tab_switch":
            previous_tab_switches = db.query(ProctorEvent).filter(
                ProctorEvent.session_id == session_id,
                ProctorEvent.event_type == "tab_switch",
            ).count()

            tab_switch_count = previous_tab_switches + 1

        event = ProctorEvent(
            session_id=session_id,
            event_type=event_type,
            description=description,
            suspicion_points=suspicion_points,
            snapshot_data=submission.snapshot_data,
            gaze_data=submission.gaze_data,
            tab_switch_count=tab_switch_count,
            created_at=get_current_utc_time(),
        )

        db.add(event)

        current_score = session.suspicion_score or 0

        session.suspicion_score = min(
            100,
            max(0, current_score + suspicion_points),
        )

        db.commit()
        db.refresh(event)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the proctoring event.",
        )

    return {
        "message": "Proctoring event recorded successfully.",
        "event_id": event.id,
        "session_id": session_id,
        "event_type": event_type,
        "suspicion_points": suspicion_points,
        "suspicion_score": session.suspicion_score,
        "tab_switch_count": tab_switch_count,
        "recorded": True,
    }


# ==========================================
# GET PROCTORING SUMMARY
# ==========================================

@router.get(
    "/{session_id}/proctoring/summary",
)
def get_proctoring_summary(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(user_token_scheme),
    db: Session = Depends(get_db),
):
    """Return proctoring history to an authorized examiner or administrator."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Staff authentication is required.",
        )

    payload = verify_token(credentials.credentials)

    if not payload or payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated staff can review proctoring history.",
        )

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication token.",
        )

    current_user = db.query(User).filter(
        User.id == user_id,
    ).first()

    if current_user is None or not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive.",
        )

    return get_proctoring_summary(
        db=db,
        session_id=session_id,
        current_user=current_user,
    )


# ==========================================
# WEBSOCKET HEARTBEAT
# ==========================================

@router.websocket(
    "/{session_id}/proctoring/heartbeat",
)
async def proctoring_heartbeat(
    websocket: WebSocket,
    session_id: int,
    token: str = Query(...),
    db: Session = Depends(get_db),
):
    """
    Maintain a WebSocket connection during an examination.

    The frontend should send a JSON heartbeat message every 10 seconds.
    """

    try:
        session = validate_proctoring_token(
            token=token,
            session_id=session_id,
            db=db,
        )

        validate_active_proctoring_session(session)

    except HTTPException as error:
        await websocket.close(
            code=4401 if error.status_code == 401 else 4403,
            reason=error.detail,
        )
        return

    await websocket.accept()

    try:
        while True:
            message = await websocket.receive_text()

            try:
                payload = json.loads(message)

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid heartbeat message.",
                })
                continue

            if (
                not isinstance(payload, dict)
                or payload.get("type") != "heartbeat"
            ):
                await websocket.send_json({
                    "type": "error",
                    "message": "Expected a heartbeat message.",
                })
                continue

            db.expire_all()

            session = db.query(ExamSession).filter(
                ExamSession.id == session_id,
            ).first()

            if session is None:
                await websocket.close(
                    code=4404,
                    reason="Exam session not found.",
                )
                break

            try:
                validate_active_proctoring_session(session)

            except HTTPException:
                await websocket.send_json({
                    "type": "session_expired",
                    "message": "The examination session is no longer active.",
                })

                await websocket.close(
                    code=4403,
                    reason="Exam session is inactive or expired.",
                )
                break

            remaining_seconds = max(
                0,
                int(
                    (
                        session.expires_at
                        - get_current_utc_time()
                    ).total_seconds()
                ),
            )

            await websocket.send_json({
                "type": "heartbeat_ack",
                "session_id": session_id,
                "server_time": get_current_utc_time().isoformat(),
                "remaining_seconds": remaining_seconds,
                "status": session.status,
            })

    except WebSocketDisconnect:
        pass

    finally:
        db.close()
