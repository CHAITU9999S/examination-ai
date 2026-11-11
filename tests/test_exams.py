from datetime import datetime, timedelta, timezone

import pytest

from app.auth import create_access_token
from app.models import User


def create_user(db, role, email):
    user = User(
        full_name=f"Test {role.title()}",
        email=email,
        password_hash="test-password-hash",
        role=role,
        is_active=True
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_auth_headers(user):
    token = create_access_token({
        "sub": str(user.id)
    })

    return {
        "Authorization": f"Bearer {token}"
    }


def valid_exam_data():
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    return {
        "title": "General Knowledge Test",
        "subject": "General Knowledge",
        "duration_minutes": 60,
        "total_questions": 4,
        "randomize_questions": True,
        "selection_rules": {
            "difficulty_counts": {
                "Easy": 2,
                "Medium": 1,
                "Hard": 1
            },
            "question_type_counts": {
                "MCQ": 2,
                "short_answer": 1,
                "long_answer": 1
            }
        },
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "negative_marking": True,
        "proctoring_enabled": True,
        "gaze_tracking_sensitivity": 0.65,
        "max_tab_switch_warnings": 3
    }


def test_examiner_can_create_exam(client, db_session):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_create@test.com"
    )

    response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Exam created successfully"
    assert "exam_id" in response.json()


def test_admin_can_create_exam(client, db_session):
    admin = create_user(
        db_session,
        "admin",
        "admin_create_exam@test.com"
    )

    response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(admin)
    )

    assert response.status_code == 200


def test_exam_configuration_is_saved_and_returned(
    client,
    db_session
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_list@test.com"
    )

    create_response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(examiner)
    )

    assert create_response.status_code == 200

    response = client.get(
        "/exams/",
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 200

    exam_id = create_response.json()["exam_id"]

    exam = next(
        item for item in response.json()
        if item["id"] == exam_id
    )

    assert exam["title"] == "General Knowledge Test"
    assert exam["subject"] == "General Knowledge"
    assert exam["duration_minutes"] == 60
    assert exam["total_questions"] == 4
    assert exam["randomize_questions"] is True
    assert exam["negative_marking"] is True
    assert exam["proctoring_enabled"] is True
    assert exam["gaze_tracking_sensitivity"] == 0.65
    assert exam["max_tab_switch_warnings"] == 3

    assert exam["selection_rules"]["difficulty_counts"]["Easy"] == 2
    assert exam["selection_rules"]["question_type_counts"]["MCQ"] == 2


def test_rejects_incomplete_distribution_rules(
    client,
    db_session
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_invalid_rules@test.com"
    )

    data = valid_exam_data()

    data["selection_rules"] = {
        "difficulty_counts": {
            "Easy": 4
        }
    }

    response = client.post(
        "/exams/",
        json=data,
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 400


def test_rejects_invalid_gaze_sensitivity(
    client,
    db_session
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_gaze@test.com"
    )

    data = valid_exam_data()
    data["gaze_tracking_sensitivity"] = 1.5

    response = client.post(
        "/exams/",
        json=data,
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 400


def test_rejects_negative_tab_switch_warnings(
    client,
    db_session
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_warnings@test.com"
    )

    data = valid_exam_data()
    data["max_tab_switch_warnings"] = -1

    response = client.post(
        "/exams/",
        json=data,
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 422


def test_student_cannot_create_exam(client, db_session):
    student = create_user(
        db_session,
        "student",
        "student_create_exam@test.com"
    )

    response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(student)
    )

    assert response.status_code == 403


def test_student_cannot_list_exams(client, db_session):
    student = create_user(
        db_session,
        "student",
        "student_list_exams@test.com"
    )

    response = client.get(
        "/exams/",
        headers=get_auth_headers(student)
    )

    assert response.status_code == 403
                                
