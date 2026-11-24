from datetime import datetime, timedelta, timezone

import pytest

from app.auth import hash_password
from app.models import Answer, Exam, ExamAssignment, ExamQuestion, ExamSession, QuestionBank, User


def create_account(db, role="student", email="single-device@test.com"):
    user = User(
        full_name="Single Device User",
        email=email,
        password_hash=hash_password("TestPassword123"),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def login(client, email="single-device@test.com"):
    return client.post(
        "/auth/login",
        json={"email": email, "password": "TestPassword123"},
    )


@pytest.mark.parametrize("role", ["student", "examiner", "admin"])
def test_new_login_invalidates_previous_device_for_every_role(
    client, db_session, role
):
    email = f"{role}-single-device@test.com"
    create_account(db_session, role=role, email=email)

    first_login = login(client, email)
    assert first_login.status_code == 200
    first_token = first_login.json()["access_token"]

    first_device = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert first_device.status_code == 200

    second_login = login(client, email)
    assert second_login.status_code == 200
    second_token = second_login.json()["access_token"]
    assert second_token != first_token

    old_device = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    assert old_device.status_code == 401
    assert "another device" in old_device.json()["detail"].lower()

    new_device = client.get(
        "/users/me",
        headers={"Authorization": f"Bearer {second_token}"},
    )
    assert new_device.status_code == 200


def test_new_login_revokes_old_exam_credentials_but_preserves_exam_and_answers(
    client, db_session
):
    student = create_account(db_session)
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    exam = Exam(
        title="Device Replacement Exam",
        subject="General Knowledge",
        duration_minutes=30,
        total_questions=1,
        randomize_questions=False,
        start_time=now - timedelta(minutes=1),
        end_time=now + timedelta(hours=1),
        created_by=None,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    question = QuestionBank(
        question_text="Saved answer must remain",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=1,
        negative_marks=0,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    db_session.add(ExamQuestion(
        exam_id=exam.id,
        question_id=question.id,
        question_order=1,
    ))
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=student.id,
        is_active=True,
    ))
    db_session.commit()

    first_login = login(client)
    assert first_login.status_code == 200
    first_login_token = first_login.json()["access_token"]

    start_response = client.post(
        f"/exam-sessions/start/{exam.id}",
        headers={"Authorization": f"Bearer {first_login_token}"},
    )
    assert start_response.status_code == 200
    started = start_response.json()
    old_exam_token = started["access_token"]
    old_refresh_token = started["refresh_token"]

    session = db_session.query(ExamSession).filter_by(
        id=started["session_id"]
    ).one()
    db_session.add(Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="My already saved answer",
    ))
    db_session.commit()

    second_login = login(client)
    assert second_login.status_code == 200
    second_login_token = second_login.json()["access_token"]

    # The previous device's examination access and refresh credentials fail.
    old_exam_access = client.get(
        f"/exam-sessions/time/{session.id}",
        headers={"Authorization": f"Bearer {old_exam_token}"},
    )
    assert old_exam_access.status_code == 401

    # The replaced device must also be blocked from writing answers and
    # sending proctoring events, not only from the timer/session endpoints.
    old_answer_write = client.post(
        f"/answers/{session.id}/{question.id}",
        headers={"Authorization": f"Bearer {old_exam_token}"},
        json={"answer_text": "1"},
    )
    assert old_answer_write.status_code == 401

    old_proctoring_event = client.post(
        f"/exam-sessions/{session.id}/proctoring/events",
        headers={"Authorization": f"Bearer {old_exam_token}"},
        json={"event_type": "tab_switch", "description": "stale device test"},
    )
    assert old_proctoring_event.status_code == 401

    old_exam_refresh = client.post(
        f"/exam-sessions/refresh/{session.id}",
        json={"refresh_token": old_refresh_token},
    )
    assert old_exam_refresh.status_code == 401

    # The exam itself and any answers already saved on the server remain intact.
    db_session.refresh(session)
    saved_answer = db_session.query(Answer).filter_by(
        session_id=session.id,
        question_id=question.id,
    ).one()
    assert session.status == "in_progress"
    assert session.selected_question_ids == [question.id]
    assert saved_answer.answer_text == "My already saved answer"
    assert session.exam_token_refresh_hash is None

    # Signing in on the new device and reopening the exam resumes the same
    # server-side session rather than creating a second attempt.
    resumed = client.post(
        f"/exam-sessions/start/{exam.id}",
        headers={"Authorization": f"Bearer {second_login_token}"},
    )
    assert resumed.status_code == 200
    assert resumed.json()["session_id"] == session.id
    assert resumed.json()["access_token"] != old_exam_token

    new_exam_access = client.get(
        f"/exam-sessions/time/{session.id}",
        headers={"Authorization": f"Bearer {resumed.json()['access_token']}"},
    )
    assert new_exam_access.status_code == 200

def test_logging_in_to_one_account_does_not_invalidate_another_account(
    client, db_session
):
    create_account(
        db_session,
        role="student",
        email="first-independent-account@test.com",
    )
    create_account(
        db_session,
        role="examiner",
        email="second-independent-account@test.com",
    )

    first_login = login(client, "first-independent-account@test.com")
    second_login = login(client, "second-independent-account@test.com")
    assert first_login.status_code == 200
    assert second_login.status_code == 200

    replacement_login = login(client, "first-independent-account@test.com")
    assert replacement_login.status_code == 200

    first_old_device = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {first_login.json()['access_token']}"
        },
    )
    second_account_device = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {second_login.json()['access_token']}"
        },
    )

    assert first_old_device.status_code == 401
    assert second_account_device.status_code == 200
