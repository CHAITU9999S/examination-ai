
from datetime import datetime, timedelta, timezone

import pytest

from app.auth import create_exam_access_token
from app.models import (
    User,
    Exam,
    ExamSession,
    ExamAssignment,
    ProctorEvent,
)


@pytest.fixture
def proctoring_data(db_session):
    """Create a student, proctored exam and active exam session."""

    student = User(
        full_name="Proctoring Test Student",
        email="proctorstudent@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )

    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    exam = Exam(
        title="Proctoring Test Examination",
        subject="General Knowledge",
        duration_minutes=30,
        total_questions=1,
        randomize_questions=False,
        proctoring_enabled=True,
        gaze_tracking_sensitivity=0.5,
        max_tab_switch_warnings=3,
        start_time=None,
        end_time=None,
        created_by=None,
    )

    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=student.id,
        is_active=True,
    ))
    db_session.commit()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now,
        expires_at=now + timedelta(minutes=30),
        status="in_progress",
        suspicion_score=0,
        selected_question_ids=[],
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    token = create_exam_access_token(
        exam_id=exam.id,
        student_id=student.id,
        session_id=session.id,
        expires_at=session.expires_at,
    )

    return {
        "student": student,
        "exam": exam,
        "session": session,
        "token": token,
    }


def proctoring_headers(token):
    return {
        "Authorization": f"Bearer {token}",
    }


def submit_event(
    client,
    data,
    event_type,
    description="Test proctoring event",
):
    return client.post(
        f"/exam-sessions/{data['session'].id}/proctoring/events",
        headers=proctoring_headers(data["token"]),
        json={
            "event_type": event_type,
            "description": description,
        },
    )


def test_student_can_submit_tab_switch_event(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "tab_switch",
        "Student switched browser tab.",
    )

    assert response.status_code in (200, 201)

    event = db_session.query(ProctorEvent).filter_by(
        session_id=data["session"].id,
        event_type="tab_switch",
    ).first()

    assert event is not None
    assert event.description == "Student switched browser tab."
    assert event.suspicion_points == pytest.approx(10)
    assert event.cumulative_suspicion_score == pytest.approx(10)


def test_tab_switch_increases_suspicion_score(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "tab_switch",
    )

    assert response.status_code in (200, 201)

    db_session.refresh(data["session"])

    assert data["session"].suspicion_score == pytest.approx(10)


def test_multiple_faces_increases_suspicion_score(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "multiple_faces",
        "Multiple faces detected.",
    )

    assert response.status_code in (200, 201)

    db_session.refresh(data["session"])

    assert data["session"].suspicion_score == pytest.approx(20)


def test_gaze_away_event_is_recorded(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "gaze_away",
        "Student looked away from the screen.",
    )

    assert response.status_code in (200, 201)

    event = db_session.query(ProctorEvent).filter_by(
        session_id=data["session"].id,
        event_type="gaze_away",
    ).first()

    assert event is not None


def test_face_not_detected_event_is_recorded(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "face_not_detected",
    )

    assert response.status_code in (200, 201)

    db_session.refresh(data["session"])

    assert data["session"].suspicion_score == pytest.approx(5)


def test_window_blur_event_is_recorded(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "window_blur",
    )

    assert response.status_code in (200, 201)

    event = db_session.query(ProctorEvent).filter_by(
        session_id=data["session"].id,
        event_type="window_blur",
    ).first()

    assert event is not None


def test_heartbeat_does_not_increase_suspicion_score(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "heartbeat",
    )

    assert response.status_code in (200, 201)

    db_session.refresh(data["session"])

    assert data["session"].suspicion_score == pytest.approx(0)


def test_multiple_events_accumulate_suspicion_score(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    first = submit_event(client, data, "tab_switch")
    second = submit_event(client, data, "multiple_faces")

    assert first.status_code in (200, 201)
    assert second.status_code in (200, 201)

    db_session.refresh(data["session"])

    assert data["session"].suspicion_score == pytest.approx(30)

    events = db_session.query(ProctorEvent).filter_by(
        session_id=data["session"].id,
    ).order_by(ProctorEvent.id.asc()).all()

    assert [event.cumulative_suspicion_score for event in events] == [
        pytest.approx(10),
        pytest.approx(30),
    ]


def test_suspicion_score_does_not_exceed_100(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    for _ in range(12):
        response = submit_event(
            client,
            data,
            "multiple_faces",
        )

        assert response.status_code in (200, 201)

    db_session.refresh(data["session"])

    assert data["session"].suspicion_score <= 100


def test_proctoring_rejects_unknown_event_type(
    client,
    proctoring_data,
):
    data = proctoring_data

    response = submit_event(
        client,
        data,
        "unknown_event",
    )

    assert response.status_code in (400, 422)


def test_inactive_student_cannot_submit_event(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    data["student"].is_active = False
    db_session.commit()

    response = submit_event(
        client,
        data,
        "tab_switch",
    )

    assert response.status_code == 403


def test_student_cannot_submit_event_for_another_session(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    another_student = User(
        full_name="Another Proctoring Student",
        email="anotherproctorstudent@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )

    db_session.add(another_student)
    db_session.commit()
    db_session.refresh(another_student)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    another_session = ExamSession(
        exam_id=data["exam"].id,
        student_id=another_student.id,
        started_at=now,
        expires_at=now + timedelta(minutes=30),
        status="in_progress",
        suspicion_score=0,
        selected_question_ids=[],
    )

    db_session.add(another_session)
    db_session.commit()
    db_session.refresh(another_session)

    response = client.post(
        f"/exam-sessions/{another_session.id}/proctoring/events",
        headers=proctoring_headers(data["token"]),
        json={
            "event_type": "tab_switch",
            "description": "Unauthorized event.",
        },
    )

    assert response.status_code == 403


def test_proctoring_disabled_exam_rejects_events(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    data["exam"].proctoring_enabled = False
    db_session.commit()

    response = submit_event(
        client,
        data,
        "tab_switch",
    )

    assert response.status_code in (400, 403)


def test_expired_session_rejects_events(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    data["session"].expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(minutes=1)
    )

    db_session.commit()

    response = submit_event(
        client,
        data,
        "tab_switch",
    )

    assert response.status_code in (400, 403, 409)


def test_submitted_session_rejects_events(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    data["session"].status = "submitted"
    data["session"].submitted_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
    )

    db_session.commit()

    response = submit_event(
        client,
        data,
        "tab_switch",
    )

    assert response.status_code in (400, 403, 409)


def test_event_history_is_available_to_examiner_or_admin(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data

    submit_event(client, data, "tab_switch")

    admin = User(
        full_name="Proctoring Admin",
        email="proctoradmin@example.com",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )

    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    from app.auth import create_access_token

    admin_token = create_access_token({
        "sub": str(admin.id),
    })

    response = client.get(
        f"/exam-sessions/{data['session'].id}/proctoring/summary",
        headers=proctoring_headers(admin_token),
    )

    assert response.status_code == 200


def test_student_cannot_access_own_proctoring_history(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data
    heartbeat_time = datetime.now(timezone.utc).replace(tzinfo=None)
    data["session"].last_heartbeat_at = heartbeat_time
    data["session"].last_heartbeat_signals = {
        "event_counts": {"tab_switch": 2, "gaze_away": 1},
        "total_event_count": 3,
        "tab_switch_count": 2,
        "auto_flagged": False,
    }
    db_session.commit()

    response = client.get(
        f"/exam-sessions/{data['session'].id}/proctoring/summary",
        headers=proctoring_headers(data["token"]),
    )

    assert response.status_code == 403
    assert "staff only" in response.json()["detail"].lower()



def test_webcam_snapshot_upload_is_rejected(
    client,
    proctoring_data,
):
    data = proctoring_data

    response = client.post(
        f"/exam-sessions/{data['session'].id}/proctoring/events",
        headers=proctoring_headers(data["token"]),
        json={
            "event_type": "face_not_detected",
            "snapshot_data": "base64-webcam-frame",
        },
    )

    assert response.status_code == 400
    assert "client-side" in response.json()["detail"]



def test_zero_tab_switch_threshold_disables_auto_flag(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data
    data["exam"].max_tab_switch_warnings = 0
    db_session.commit()

    submit_response = submit_event(client, data, "tab_switch")
    assert submit_response.status_code in (200, 201)

    admin = User(
        full_name="Zero Threshold Admin",
        email="zero-threshold-admin@example.com",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    from app.auth import create_access_token

    token = create_access_token({"sub": str(admin.id)})
    response = client.get(
        f"/exam-sessions/{data['session'].id}/proctoring/summary",
        headers=proctoring_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["auto_flag_threshold"] == 0
    assert response.json()["auto_flagged"] is False


def test_positive_tab_switch_threshold_flags_session(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data
    data["exam"].max_tab_switch_warnings = 1
    db_session.commit()

    submit_response = submit_event(client, data, "tab_switch")
    assert submit_response.status_code in (200, 201)

    admin = User(
        full_name="Threshold Admin",
        email="threshold-admin@example.com",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    from app.auth import create_access_token

    token = create_access_token({"sub": str(admin.id)})
    response = client.get(
        f"/exam-sessions/{data['session'].id}/proctoring/summary",
        headers=proctoring_headers(token),
    )

    assert response.status_code == 200
    assert response.json()["auto_flag_threshold"] == 1
    assert response.json()["auto_flagged"] is True

def test_heartbeat_uses_server_persisted_events_not_client_counters(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data
    data["exam"].max_tab_switch_warnings = 1
    db_session.commit()

    event_response = submit_event(client, data, "tab_switch")
    assert event_response.status_code in (200, 201)

    websocket_url = (
        f"/exam-sessions/{data['session'].id}/proctoring/heartbeat"
        f"?token={data['token']}"
    )

    with client.websocket_connect(websocket_url) as websocket:
        websocket.send_json({
            "type": "heartbeat",
            "signals": {
                "event_counts": {
                    "tab_switch": 999,
                    "multiple_faces": 999,
                },
                "total_event_count": 1998,
                "tab_switch_count": 999,
                "auto_flagged": True,
            },
        })

        acknowledgement = websocket.receive_json()

    assert acknowledgement["type"] == "heartbeat_ack"
    assert acknowledgement["server_event_counts"] == {
        "tab_switch": 1,
    }
    assert acknowledgement["server_suspicion_score"] == pytest.approx(10)
    assert acknowledgement["server_auto_flagged"] is True
    assert acknowledgement["signals_received"]["tab_switch_count"] == 1
    assert (
        acknowledgement["signals_received"]["client_reported_signals"]
        ["tab_switch_count"]
        == 999
    )

    stored_session = db_session.query(ExamSession).filter_by(
        id=data["session"].id,
    ).one()
    assert stored_session.last_heartbeat_signals["tab_switch_count"] == 1
    assert stored_session.last_heartbeat_signals["auto_flagged"] is True



def test_admin_can_list_flagged_sessions_without_webcam_snapshots(
    client,
    db_session,
    proctoring_data,
):
    data = proctoring_data
    data["exam"].max_tab_switch_warnings = 1
    db_session.commit()
    event_response = submit_event(client, data, "tab_switch")
    assert event_response.status_code in (200, 201)

    admin = User(
        full_name="Flagged Review Admin",
        email="flagged-review-admin@example.com",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(admin)

    from app.auth import create_access_token
    token = create_access_token({"sub": str(admin.id)})
    response = client.get(
        "/exam-sessions/proctoring/flagged",
        headers=proctoring_headers(token),
    )

    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert len(sessions) == 1
    flagged = sessions[0]
    assert flagged["session_id"] == data["session"].id
    assert flagged["auto_flagged"] is True
    assert flagged["webcam_snapshots_available"] is False
    assert "snapshot_data" not in flagged["events"][0]


def test_student_cannot_list_flagged_sessions(
    client,
    proctoring_data,
):
    data = proctoring_data
    from app.auth import create_access_token

    student_token = create_access_token({"sub": str(data["student"].id)})
    response = client.get(
        "/exam-sessions/proctoring/flagged",
        headers=proctoring_headers(student_token),
    )
    assert response.status_code == 403
