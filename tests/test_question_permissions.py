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


def test_student_cannot_list_questions(client, db_session):
    student = create_user(
        db_session, "student", "student_questions@test.com"
    )

    response = client.get(
        "/questions/",
        headers=get_auth_headers(student)
    )

    assert response.status_code == 403


def test_student_cannot_create_questions(client, db_session):
    student = create_user(
        db_session, "student", "student_create@test.com"
    )

    question_data = {
        "question_text": "What is the capital of India?",
        "question_type": "MCQ",
        "subject": "General Knowledge",
        "difficulty": "Easy",
        "marks": 2,
        "negative_marks": 0.5,
        "options": ["New Delhi", "Mumbai"],
        "correct_option_index": 0
    }

    response = client.post(
        "/questions/",
        json=question_data,
        headers=get_auth_headers(student)
    )

    assert response.status_code == 403


def test_student_cannot_delete_questions(client, db_session):
    student = create_user(
        db_session, "student", "student_delete@test.com"
    )

    response = client.delete(
        "/questions/999",
        headers=get_auth_headers(student)
    )

    assert response.status_code == 403


@pytest.mark.parametrize("role", ["examiner", "admin"])
def test_examiner_and_admin_can_list_questions(
    client, db_session, role
):
    user = create_user(
        db_session,
        role,
        f"{role}_questions@test.com"
    )

    response = client.get(
        "/questions/",
        headers=get_auth_headers(user)
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)
  
