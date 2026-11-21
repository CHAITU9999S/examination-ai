import pytest

from app.auth import create_access_token
from app.models import User, QuestionBank, Option


def create_user(db, role, email):
    user = User(
        full_name=f"Test {role.title()}",
        email=email,
        password_hash="test-password-hash",
        role=role,
        is_active=True,
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


def create_question(db, user):
    question = QuestionBank(
        question_text="What is the capital of India?",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=2,
        negative_marks=0.5,
        created_by=user.id,
    )

    db.add(question)
    db.commit()
    db.refresh(question)

    option = Option(
        question_id=question.id,
        option_text="New Delhi",
        is_correct=True,
    )

    db.add(option)
    db.commit()

    return question


def valid_question_data():
    return {
        "question_text": "What is the capital of India?",
        "question_type": "MCQ",
        "subject": "General Knowledge",
        "difficulty": "easy",
        "marks": 2,
        "negative_marks": 0.5,
        "options": ["New Delhi", "Mumbai"],
        "correct_option_index": 0,
    }


def test_student_cannot_list_questions(client, db_session):
    student = create_user(
        db_session, "student", "student_questions@test.com"
    )

    response = client.get(
        "/questions/",
        headers=get_auth_headers(student),
    )

    assert response.status_code == 403


def test_student_cannot_create_questions(client, db_session):
    student = create_user(
        db_session, "student", "student_create@test.com"
    )

    response = client.post(
        "/questions/",
        json=valid_question_data(),
        headers=get_auth_headers(student),
    )

    assert response.status_code == 403


def test_student_cannot_delete_questions(client, db_session):
    student = create_user(
        db_session, "student", "student_delete@test.com"
    )

    response = client.delete(
        "/questions/999",
        headers=get_auth_headers(student),
    )

    assert response.status_code == 403


@pytest.mark.parametrize("role", ["examiner", "admin"])
def test_examiner_and_admin_can_list_questions(
    client, db_session, role
):
    user = create_user(
        db_session,
        role,
        f"{role}_questions@test.com",
    )

    response = client.get(
        "/questions/",
        headers=get_auth_headers(user),
    )

    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.parametrize("role", ["examiner", "admin"])
def test_examiner_and_admin_can_create_questions(
    client, db_session, role
):
    user = create_user(
        db_session,
        role,
        f"{role}_create@test.com",
    )

    response = client.post(
        "/questions/",
        json=valid_question_data(),
        headers=get_auth_headers(user),
    )

    assert response.status_code == 201


@pytest.mark.parametrize("role", ["examiner", "admin"])
def test_examiner_and_admin_can_delete_questions(
    client, db_session, role
):
    user = create_user(
        db_session,
        role,
        f"{role}_delete@test.com",
    )

    question = create_question(db_session, user)

    response = client.delete(
        f"/questions/{question.id}",
        headers=get_auth_headers(user),
    )

    assert response.status_code == 200

    remaining_question = (
        db_session.query(QuestionBank)
        .filter(QuestionBank.id == question.id)
        .first()
    )

    assert remaining_question is None
    


def test_admin_cannot_delete_another_users_question(client, db_session):
    examiner = create_user(
        db_session, "examiner", "question_owner@test.com"
    )
    admin = create_user(
        db_session, "admin", "question_admin@test.com"
    )
    question = create_question(db_session, examiner)

    response = client.delete(
        f"/questions/{question.id}",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == 403
    assert db_session.query(QuestionBank).filter(
        QuestionBank.id == question.id
    ).first() is not None
