
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
    Result,
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
    "fullscreen_exit": 0,
    "heartbeat": 0,
}

MAX_SNAPSHOT_LENGTH = 100000


# ==========================================
# REQUEST SCHEMA
# ==========================================

class IntegrityDecisionSubmission(BaseModel):
    decision: str = Field(pattern="^(pass|disqualify)$")
    reason: str | None = Field(default=None, max_length=2000)


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

    # Proctoring is mandatory for every active examination session.

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


@router.get("/proctoring/analytics")
def get_exam_proctoring_analytics(
    exam_id: int = Query(..., gt=0),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return cohort-level proctoring aggregates for an exam visible to this staff user."""
    role = getattr(current_user.role, "value", current_user.role)
    if role not in {"admin", "examiner"} or not current_user.is_active:
        raise HTTPException(status_code=403, detail="Only active Admins and Examiners can view proctoring analytics.")

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    if role == "examiner" and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only view analytics for examinations you created.")

    sessions = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.status.in_(["submitted", "auto_submitted", "expired"]),
    ).order_by(ExamSession.id.asc()).all()
    session_ids = [session.id for session in sessions]
    event_rows = db.query(
        ProctorEvent.session_id,
        ProctorEvent.event_type,
        func.count(ProctorEvent.id),
    ).filter(
        ProctorEvent.session_id.in_(session_ids or [-1]),
    ).group_by(
        ProctorEvent.session_id,
        ProctorEvent.event_type,
    ).all()

    counts_by_session: dict[int, dict[str, int]] = {}
    for session_id, event_type, count in event_rows:
        counts_by_session.setdefault(session_id, {})[event_type] = int(count)

    total = len(sessions)
    def percentage(predicate):
        return round(sum(1 for session in sessions if predicate(session, counts_by_session.get(session.id, {}))) / total * 100, 1) if total else None

    monitoring_totals = {
        "monitoring_seconds": 0,
        "face_present_seconds": 0,
        "gaze_measured_seconds": 0,
        "gaze_on_screen_seconds": 0,
    }
    for session in sessions:
        signals = session.last_heartbeat_signals or {}
        metrics = signals.get("client_reported_monitoring_metrics", {})
        if not isinstance(metrics, dict):
            continue
        for key in monitoring_totals:
            value = metrics.get(key, 0)
            if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
                monitoring_totals[key] += value

    def rate(numerator: str, denominator: str):
        total_seconds = monitoring_totals[denominator]
        return round(monitoring_totals[numerator] / total_seconds * 100, 1) if total_seconds else None

    expected_monitoring_seconds = sum(
        max(0, int(((session.submitted_at or session.expires_at) - session.started_at).total_seconds()))
        for session in sessions
        if session.started_at is not None and (session.submitted_at is not None or session.expires_at is not None)
    )
    monitoring_coverage = (
        round(min(100.0, monitoring_totals["monitoring_seconds"] / expected_monitoring_seconds * 100), 1)
        if expected_monitoring_seconds > 0 else None
    )

    bands = [
        {"label": "0–20", "count": 0},
        {"label": "21–40", "count": 0},
        {"label": "41–60", "count": 0},
        {"label": "61–80", "count": 0},
        {"label": "81–100", "count": 0},
    ]
    for session in sessions:
        score = max(0.0, min(100.0, float(session.suspicion_score or 0)))
        index = min(4, int(score // 20))
        bands[index]["count"] += 1

    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "cohort_size": total,
        "metrics": {
            "no_face_loss_events": percentage(lambda _s, c: c.get("face_not_detected", 0) == 0),
            "no_gaze_away_events": percentage(lambda _s, c: c.get("gaze_away", 0) == 0),
            "no_tab_switches": percentage(lambda _s, c: c.get("tab_switch", 0) == 0),
            "no_multiple_face_events": percentage(lambda _s, c: c.get("multiple_faces", 0) == 0),
            "high_suspicion_over_60": percentage(lambda s, _c: float(s.suspicion_score or 0) > 60),
            "face_present_rate": rate("face_present_seconds", "monitoring_seconds"),
            "gaze_on_screen_rate": rate("gaze_on_screen_seconds", "gaze_measured_seconds"),
            "monitoring_coverage_rate": monitoring_coverage,
        },
        "monitoring_totals": monitoring_totals,
        "score_distribution": bands,
        "metric_note": "Event percentages are the share of finished sessions with no corresponding event. Face-present and gaze-on-screen rates are browser-side detector estimates from one-second samples; monitoring coverage compares sampled seconds with elapsed session time. These are indicative metrics, not tamper-proof proof of candidate conduct.",
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
                    "snapshot_available": bool(event.snapshot_data),
                }
                for event in events
            ],
            "webcam_snapshots_available": any(event.snapshot_data for event in events),
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


@router.post("/{session_id}/proctoring/integrity-decision")
def record_integrity_decision(
    session_id: int,
    submission: IntegrityDecisionSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record an auditable examiner integrity decision without altering grading or publication."""
    role = getattr(current_user.role, "value", current_user.role)
    if role not in {"admin", "examiner"} or not current_user.is_active:
        raise HTTPException(status_code=403, detail="Only active Admins and Examiners can record integrity decisions.")

    session = db.query(ExamSession).filter(ExamSession.id == session_id).with_for_update().first()
    if session is None:
        raise HTTPException(status_code=404, detail="Examination session not found.")
    if session.status not in {"submitted", "auto_submitted", "expired"}:
        raise HTTPException(status_code=409, detail="Integrity decisions can be recorded only for submitted or expired examination sessions.")
    published_result = db.query(Result.id).filter(
        Result.session_id == session_id,
        Result.is_published.is_(True),
    ).first()
    if published_result is not None:
        raise HTTPException(status_code=409, detail="The result is already published. Integrity decisions must be completed before publication.")

    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    if role == "examiner" and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can only decide integrity for your own examinations.")
    if submission.decision == "disqualify" and not (submission.reason or "").strip():
        raise HTTPException(status_code=422, detail="A reason is required when disqualifying a session.")

    signals = dict(session.last_heartbeat_signals or {})
    existing_history = signals.get("integrity_decision_history", [])
    history = list(existing_history) if isinstance(existing_history, list) else []
    decision = {
        "decision": submission.decision,
        "reason": (submission.reason or "").strip() or None,
        "decided_by_user_id": current_user.id,
        "decided_by_name": current_user.full_name,
        "decided_by_role": role,
        "decided_at": get_current_utc_time().isoformat(),
    }
    history.append(decision)
    signals["integrity_decision"] = decision
    signals["integrity_decision_history"] = history[-20:]
    session.last_heartbeat_signals = signals
    db.commit()
    return {
        "message": "Integrity decision recorded. Examination marks and result publication were not changed.",
        "integrity_decision": decision,
        "integrity_decision_history": signals["integrity_decision_history"],
    }


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
        "integrity_decision": (history["last_heartbeat_signals"] or {}).get("integrity_decision"),
        "integrity_decision_history": (history["last_heartbeat_signals"] or {}).get("integrity_decision_history", []),
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
                "snapshot_data": event.snapshot_data,
            }
            for event in history["events"]
        ],
        "webcam_snapshots_available": any(event.snapshot_data for event in history["events"]),
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

            raw_monitoring_metrics = raw_signals.get("monitoring_metrics", {})
            if not isinstance(raw_monitoring_metrics, dict):
                await websocket.send_json({
                    "type": "error",
                    "message": "Heartbeat monitoring_metrics must be a JSON object.",
                })
                continue

            metric_names = (
                "monitoring_seconds",
                "face_present_seconds",
                "multiple_face_seconds",
                "face_missing_seconds",
                "gaze_measured_seconds",
                "gaze_on_screen_seconds",
                "gaze_away_seconds",
            )
            monitoring_metrics = {}
            invalid_metrics = False
            for metric_name in metric_names:
                metric_value = raw_monitoring_metrics.get(metric_name, 0)
                if (
                    isinstance(metric_value, bool)
                    or not isinstance(metric_value, int)
                    or metric_value < 0
                ):
                    invalid_metrics = True
                    break
                monitoring_metrics[metric_name] = min(metric_value, 36000)

            if (
                invalid_metrics
                or monitoring_metrics["face_present_seconds"] > monitoring_metrics["monitoring_seconds"]
                or monitoring_metrics["multiple_face_seconds"] > monitoring_metrics["monitoring_seconds"]
                or monitoring_metrics["face_missing_seconds"] > monitoring_metrics["monitoring_seconds"]
                or monitoring_metrics["gaze_measured_seconds"] > monitoring_metrics["monitoring_seconds"]
                or monitoring_metrics["gaze_on_screen_seconds"] > monitoring_metrics["gaze_measured_seconds"]
                or monitoring_metrics["gaze_away_seconds"] > monitoring_metrics["gaze_measured_seconds"]
                or monitoring_metrics["gaze_on_screen_seconds"] + monitoring_metrics["gaze_away_seconds"] > monitoring_metrics["gaze_measured_seconds"]
            ):
                await websocket.send_json({
                    "type": "error",
                    "message": "Heartbeat monitoring metrics are invalid.",
                })
                continue

            normalized_signals = {
                "event_counts": normalized_counts,
                "total_event_count": min(total_event_count, 1000000),
                "tab_switch_count": min(tab_switch_count, 1000000),
                "auto_flagged": auto_flagged,
                "monitoring_metrics": monitoring_metrics,
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
                # These are browser-side detector estimates, not tamper-proof evidence.
                "client_reported_monitoring_metrics": monitoring_metrics,
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
