
import hmac
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
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Exam,
    ExamAssignment,
    ExamSession,
    ProctorEvent,
    User,
)
from app.services.proctoring_service import (
    get_proctoring_summary as get_staff_proctoring_summary,
    get_proctoring_history_for_staff,
    record_proctor_event,
)


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

    # A replaced login must lose access to proctoring events and heartbeat too.
    token_auth_session_id = payload.get("auth_session_id")
    if student.active_session_id:
        if (
            not isinstance(token_auth_session_id, str)
            or not hmac.compare_digest(token_auth_session_id, student.active_session_id)
        ):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="This examination was signed out because your account was used to sign in on another device.",
            )
    elif token_auth_session_id is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="This examination login session is no longer active.",
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


def validate_proctoring_enabled(
    session: ExamSession,
    db: Session,
):
    """Ensure proctoring is enabled for the session's examination."""

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

    return exam


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

    result = record_proctor_event(
        db=db,
        session_id=session_id,
        current_user=session.student,
        event_type=submission.event_type.strip().lower(),
        description=(
            submission.description.strip()
            if submission.description
            else None
        ),
        gaze_data=submission.gaze_data,
        snapshot_data=submission.snapshot_data,
    )

    return {
        **result,
        "session_id": session_id,
        "recorded": True,
    }

def _exam_attribution(exam: Exam, student_id: int, db: Session) -> dict:
    creator = db.query(User).filter(User.id == exam.created_by).first()
    assignment = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam.id,
        ExamAssignment.student_id == student_id,
    ).first()
    assigner = (
        db.query(User).filter(User.id == assignment.assigned_by).first()
        if assignment is not None else None
    )
    return {
        "creator_name": creator.full_name if creator else "Unknown",
        "creator_role": creator.role if creator else None,
        "assigned_by_name": assigner.full_name if assigner else "Unknown",
        "assigned_by_role": assigner.role if assigner else None,
    }


# ==========================================
# LIST FLAGGED EXAMINATION SESSIONS
# ==========================================

@router.get("/proctoring/flagged")
def list_flagged_proctoring_sessions(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List suspicious sessions for authorized examiners and Admins."""

    role = getattr(current_user.role, "value", current_user.role)
    if role not in {"admin", "examiner"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only examiners and administrators can review flagged sessions.",
        )

    query = db.query(
        ExamSession,
        Exam,
        User,
    ).join(
        Exam,
        ExamSession.exam_id == Exam.id,
    ).join(
        User,
        ExamSession.student_id == User.id,
    )

    if role == "examiner":
        query = query.filter(Exam.created_by == current_user.id)

    rows = query.order_by(
        ExamSession.started_at.desc(),
        ExamSession.id.desc(),
    ).limit(250).all()

    flagged_sessions = []
    for session, exam, student in rows:
        event_rows = db.query(
            ProctorEvent.event_type,
            func.count(ProctorEvent.id),
        ).filter(
            ProctorEvent.session_id == session.id,
        ).group_by(
            ProctorEvent.event_type,
        ).all()

        event_counts = {
            event_type: int(count)
            for event_type, count in event_rows
        }
        tab_switch_count = event_counts.get("tab_switch", 0)
        threshold = (
            int(exam.max_tab_switch_warnings)
            if exam.max_tab_switch_warnings is not None
            else None
        )
        auto_flagged = (
            threshold is not None
            and threshold > 0
            and tab_switch_count >= threshold
        )
        score = float(session.suspicion_score or 0)
        flagged = auto_flagged or score >= 50

        if not flagged:
            continue

        events = db.query(ProctorEvent).filter(
            ProctorEvent.session_id == session.id,
        ).order_by(
            ProctorEvent.created_at.desc(),
            ProctorEvent.id.desc(),
        ).limit(20).all()

        flagged_sessions.append({
            "session_id": session.id,
            "exam_id": exam.id,
            "exam_title": exam.title,
            **_exam_attribution(exam, student.id, db),
            "student_id": student.id,
            "student_name": student.full_name,
            "session_status": session.status,
            "started_at": session.started_at,
            "submitted_at": session.submitted_at,
            "suspicion_score": score,
            "auto_flagged": auto_flagged,
            "tab_switch_count": tab_switch_count,
            "tab_switch_threshold": threshold,
            "event_counts": event_counts,
            "events": [
                {
                    "event_id": event.id,
                    "event_type": event.event_type,
                    "description": event.description,
                    "suspicion_points": event.suspicion_points,
                    "cumulative_suspicion_score": event.cumulative_suspicion_score,
                    "created_at": event.created_at,
                }
                for event in events
            ],
            # Webcam frames are intentionally not uploaded or stored.
            "webcam_snapshots_available": False,
        })

    return {
        "total_flagged": len(flagged_sessions),
        "sessions": flagged_sessions,
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

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
        )

    if payload.get("token_type") == "exam":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Proctoring history is available to authorized staff only.",
        )

    if payload.get("token_type") != "access":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unsupported authentication token type.",
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

    return get_staff_proctoring_summary(
        db=db,
        session_id=session_id,
        current_user=current_user,
    )


@router.get("/{session_id}/proctoring/history")
def get_staff_proctoring_history(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return all proctoring events for one session to its authorized staff."""
    history = get_proctoring_history_for_staff(
        db=db,
        session_id=session_id,
        current_user=current_user,
    )
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first() if session else None
    student = db.query(User).filter(User.id == session.student_id).first() if session else None
    return {
        "session_id": session_id,
        "exam_id": history["exam_id"],
        "exam_title": exam.title if exam else "Unknown examination",
        **(_exam_attribution(exam, history["student_id"], db) if exam else {}),
        "student_id": history["student_id"],
        "student_name": student.full_name if student else "Unknown student",
        "session_status": history["session_status"],
        "started_at": session.started_at if session else None,
        "submitted_at": session.submitted_at if session else None,
        "suspicion_score": history["suspicion_score"],
        "last_heartbeat_at": history["last_heartbeat_at"],
        "last_heartbeat_signals": history["last_heartbeat_signals"],
        "tab_switch_count": history["tab_switch_count"],
        "tab_switch_threshold": history["auto_flag_threshold"],
        "auto_flagged": history["auto_flagged"],
        "event_counts": {
            event_type: sum(1 for event in history["events"] if event.event_type == event_type)
            for event_type in {event.event_type for event in history["events"]}
        },
        "total_events": history["total_events"],
        "events": [
            {
                "event_id": event.id,
                "event_type": event.event_type,
                "description": event.description,
                "suspicion_points": event.suspicion_points,
                "cumulative_suspicion_score": event.cumulative_suspicion_score,
                "created_at": event.created_at,
            }
            for event in history["events"]
        ],
        "webcam_snapshots_available": False,
    }


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
        validate_proctoring_enabled(session, db)

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

            # The WebSocket must not keep an expired access token alive.
            # The browser rotates its token periodically and reconnects.
            if not verify_token(
                token,
                expected_token_type="exam",
            ):
                await websocket.send_json({
                    "type": "token_expired",
                    "message": "The examination access token expired. Renew the token and reconnect.",
                })
                await websocket.close(
                    code=4401,
                    reason="Exam access token expired.",
                )
                break

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

            raw_signals = payload.get("signals", {})
            if not isinstance(raw_signals, dict):
                await websocket.send_json({
                    "type": "error",
                    "message": "Heartbeat signals must be a JSON object.",
                })
                continue

            event_counts = raw_signals.get("event_counts", {})
            if not isinstance(event_counts, dict):
                await websocket.send_json({
                    "type": "error",
                    "message": "Heartbeat event_counts must be a JSON object.",
                })
                continue

            allowed_event_types = set(EVENT_SUSPICION_POINTS) - {"heartbeat"}
            normalized_counts = {}
            invalid_counts = False
            for event_type, count in event_counts.items():
                if (
                    event_type not in allowed_event_types
                    or isinstance(count, bool)
                    or not isinstance(count, int)
                    or count < 0
                ):
                    invalid_counts = True
                    break
                normalized_counts[event_type] = min(count, 1000000)

            total_event_count = raw_signals.get("total_event_count", 0)
            tab_switch_count = raw_signals.get("tab_switch_count", 0)
            auto_flagged = raw_signals.get("auto_flagged", False)
            if (
                invalid_counts
                or isinstance(total_event_count, bool)
                or not isinstance(total_event_count, int)
                or total_event_count < 0
                or isinstance(tab_switch_count, bool)
                or not isinstance(tab_switch_count, int)
                or tab_switch_count < 0
                or not isinstance(auto_flagged, bool)
            ):
                await websocket.send_json({
                    "type": "error",
                    "message": "Heartbeat signal summary is invalid.",
                })
                continue

            normalized_signals = {
                "event_counts": normalized_counts,
                "total_event_count": min(total_event_count, 1000000),
                "tab_switch_count": min(tab_switch_count, 1000000),
                "auto_flagged": auto_flagged,
            }

            db.expire_all()

            # Revalidate the login identity and assignment on every heartbeat.
            # This closes an already-open socket if the student signs in on
            # another device or the examination assignment is revoked.
            try:
                session = validate_proctoring_token(
                    token=token,
                    session_id=session_id,
                    db=db,
                )
                validate_active_proctoring_session(session)
                validate_proctoring_enabled(session, db)
            except HTTPException as error:
                await websocket.send_json({
                    "type": "session_expired",
                    "message": error.detail,
                })
                await websocket.close(
                    code=4401 if error.status_code == 401 else 4403,
                    reason=error.detail,
                )
                break

            heartbeat_time = get_current_utc_time()

            # Heartbeat counters originate in the browser and can be forged.
            # Keep them as diagnostic client telemetry, but calculate the
            # official event summary and auto-flag state from persisted events.
            persisted_counts = db.query(
                ProctorEvent.event_type,
                func.count(ProctorEvent.id),
            ).filter(
                ProctorEvent.session_id == session_id,
            ).group_by(
                ProctorEvent.event_type,
            ).all()

            server_event_counts = {
                event_type: int(count)
                for event_type, count in persisted_counts
            }
            server_total_event_count = sum(server_event_counts.values())
            server_tab_switch_count = server_event_counts.get("tab_switch", 0)

            exam = db.query(Exam).filter(
                Exam.id == session.exam_id,
            ).first()
            flag_threshold = (
                int(exam.max_tab_switch_warnings)
                if exam is not None and exam.max_tab_switch_warnings is not None
                else None
            )
            server_auto_flagged = (
                flag_threshold is not None
                and flag_threshold > 0
                and server_tab_switch_count >= flag_threshold
            )

            authoritative_signals = {
                "event_counts": server_event_counts,
                "total_event_count": server_total_event_count,
                "tab_switch_count": server_tab_switch_count,
                "auto_flagged": server_auto_flagged,
                "auto_flag_threshold": flag_threshold,
                "client_reported_signals": normalized_signals,
            }

            session.last_heartbeat_at = heartbeat_time
            session.last_heartbeat_signals = authoritative_signals
            db.commit()

            remaining_seconds = max(
                0,
                int(
                    (
                        session.expires_at
                        - heartbeat_time
                    ).total_seconds()
                ),
            )

            await websocket.send_json({
                "type": "heartbeat_ack",
                "session_id": session_id,
                "server_time": heartbeat_time.isoformat(),
                "last_heartbeat_at": heartbeat_time.isoformat(),
                "signals_received": authoritative_signals,
                "server_suspicion_score": float(session.suspicion_score or 0),
                "server_event_counts": server_event_counts,
                "server_auto_flagged": server_auto_flagged,
                "remaining_seconds": remaining_seconds,
                "status": session.status,
            })

    except WebSocketDisconnect:
        pass

    finally:
        db.close()
