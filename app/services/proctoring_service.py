
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Exam,
    ExamSession,
    ProctorEvent,
    User,
)


# ==========================================
# PROCTORING CONFIGURATION
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

MAX_SUSPICION_SCORE = 100

MAX_DESCRIPTION_LENGTH = 2000
MAX_SNAPSHOT_LENGTH = 100000


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def _value(value):
    """Convert an enum value to its underlying string."""

    return getattr(value, "value", value)


def _get_session_or_404(
    db: Session,
    session_id: int,
):
    """Retrieve an examination session."""

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination session not found.",
        )

    return session


def _get_exam_or_404(
    db: Session,
    exam_id: int,
):
    """Retrieve an examination."""

    exam = db.query(Exam).filter(
        Exam.id == exam_id,
    ).first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination not found.",
        )

    return exam


def _get_role(user: User):
    """Get a user's role."""

    return _value(user.role)


def _require_student_session_access(
    session: ExamSession,
    current_user: User,
):
    """Ensure that a student accesses only their own session."""

    if _get_role(current_user) != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can submit proctoring events.",
        )

    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive.",
        )

    if session.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another student's session.",
        )


def _validate_proctoring_enabled(
    db: Session,
    session: ExamSession,
):
    """Check whether proctoring is enabled for the examination."""

    exam = _get_exam_or_404(
        db,
        session.exam_id,
    )

    if not exam.proctoring_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Proctoring is not enabled for this examination.",
        )

    return exam


def _validate_event_data(
    event_type: str,
    description,
    gaze_data,
    snapshot_data,
):
    """Validate submitted proctoring event data."""

    if not isinstance(event_type, str):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Event type must be text.",
        )

    if event_type not in EVENT_SUSPICION_POINTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported proctoring event type.",
        )

    if description is not None:
        if not isinstance(description, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event description must be text.",
            )

        if len(description) > MAX_DESCRIPTION_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Event description is too long.",
            )

    if gaze_data is not None and not isinstance(gaze_data, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Gaze data must be a JSON object.",
        )

    # The project requirements specify that webcam frames stay in the
    # browser. Only derived signals may be sent to the backend.
    if snapshot_data is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Webcam snapshots must remain client-side; submit derived proctoring signals only.",
        )


# ==========================================
# RECORD PROCTORING EVENT
# ==========================================

def record_proctor_event(
    db: Session,
    session_id: int,
    current_user: User,
    event_type: str,
    description=None,
    gaze_data=None,
    snapshot_data=None,
):
    """
    Record a proctoring event for an active examination.

    Suspicion points are calculated by the server.
    Client-submitted suspicion scores are never trusted.
    """

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).with_for_update().first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination session not found.",
        )

    _require_student_session_access(
        session,
        current_user,
    )

    _validate_proctoring_enabled(
        db,
        session,
    )

    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The examination session is not active.",
        )

    now = datetime.utcnow()

    if session.expires_at <= now:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The examination session has expired.",
        )

    _validate_event_data(
        event_type,
        description,
        gaze_data,
        snapshot_data,
    )

    suspicion_points = EVENT_SUSPICION_POINTS[event_type]

    try:
        tab_switch_count = None

        if event_type == "tab_switch":
            previous_count = (
                db.query(func.count(ProctorEvent.id))
                .filter(
                    ProctorEvent.session_id == session_id,
                    ProctorEvent.event_type == "tab_switch",
                )
                .scalar()
            )

            tab_switch_count = previous_count + 1

        current_score = float(session.suspicion_score or 0)
        cumulative_score = min(
            MAX_SUSPICION_SCORE,
            current_score + suspicion_points,
        )

        event = ProctorEvent(
            session_id=session_id,
            event_type=event_type,
            description=description,
            suspicion_points=suspicion_points,
            cumulative_suspicion_score=cumulative_score,
            gaze_data=gaze_data,
            # Webcam frames are intentionally never persisted or uploaded.
            snapshot_data=None,
            tab_switch_count=tab_switch_count,
            created_at=now,
        )

        db.add(event)
        session.suspicion_score = cumulative_score

        db.commit()
        db.refresh(event)

        return {
            "message": "Proctoring event recorded successfully.",
            "event_id": event.id,
            "event_type": event.event_type,
            "suspicion_points": event.suspicion_points,
            "cumulative_suspicion_score": event.cumulative_suspicion_score,
            "suspicion_score": session.suspicion_score,
            "tab_switch_count": tab_switch_count,
        }

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while recording the proctoring event.",
        )


# ==========================================
# GET STUDENT PROCTORING HISTORY
# ==========================================

def get_student_proctoring_history(
    db: Session,
    session_id: int,
    current_user: User,
):
    """Allow a student to view their own proctoring history."""

    session = _get_session_or_404(
        db,
        session_id,
    )

    if _get_role(current_user) != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This operation is available to students only.",
        )

    if session.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot access another student's history.",
        )

    events = db.query(ProctorEvent).filter(
        ProctorEvent.session_id == session_id,
    ).order_by(
        ProctorEvent.created_at.asc(),
        ProctorEvent.id.asc(),
    ).all()

    return {
        "session_id": session_id,
        "suspicion_score": session.suspicion_score or 0,
        "last_heartbeat_at": session.last_heartbeat_at,
        "last_heartbeat_signals": session.last_heartbeat_signals,
        "total_events": len(events),
        "events": events,
    }


# ==========================================
# GET EXAMINER / ADMIN PROCTORING HISTORY
# ==========================================

def get_proctoring_history_for_staff(
    db: Session,
    session_id: int,
    current_user: User,
):
    """
    Allow the examination owner or an administrator
    to review a student's proctoring history.
    """

    session = _get_session_or_404(
        db,
        session_id,
    )

    role = _get_role(current_user)

    if role not in {"admin", "examiner"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and examiners can review this history.",
        )

    exam = _get_exam_or_404(
        db,
        session.exam_id,
    )

    if role == "examiner" and exam.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only review proctoring records for your own exams.",
        )

    events = db.query(ProctorEvent).filter(
        ProctorEvent.session_id == session_id,
    ).order_by(
        ProctorEvent.created_at.asc(),
        ProctorEvent.id.asc(),
    ).all()

    tab_switch_count = sum(
        1
        for event in events
        if event.event_type == "tab_switch"
    )

    return {
        "session_id": session_id,
        "exam_id": session.exam_id,
        "student_id": session.student_id,
        "session_status": session.status,
        "suspicion_score": session.suspicion_score or 0,
        "last_heartbeat_at": session.last_heartbeat_at,
        "last_heartbeat_signals": session.last_heartbeat_signals,
        "tab_switch_count": tab_switch_count,
        "auto_flagged": (
            tab_switch_count >= max(0, int(exam.max_tab_switch_warnings or 0))
            if exam.max_tab_switch_warnings is not None
            else False
        ),
        "total_events": len(events),
        "events": events,
    }


# ==========================================
# GET PROCTORING SUMMARY
# ==========================================

def get_proctoring_summary(
    db: Session,
    session_id: int,
    current_user: User,
):
    """Return event counts and suspicion score for authorized staff."""

    history = get_proctoring_history_for_staff(
        db,
        session_id,
        current_user,
    )

    event_counts = {}

    for event in history["events"]:
        event_counts[event.event_type] = (
            event_counts.get(event.event_type, 0) + 1
        )

    return {
        "session_id": session_id,
        "exam_id": history["exam_id"],
        "student_id": history["student_id"],
        "session_status": history["session_status"],
        "suspicion_score": history["suspicion_score"],
        "last_heartbeat_at": history["last_heartbeat_at"],
        "last_heartbeat_signals": history["last_heartbeat_signals"],
        "tab_switch_count": history["tab_switch_count"],
        "auto_flagged": history["auto_flagged"],
        "total_events": history["total_events"],
        "event_counts": event_counts,
    }
