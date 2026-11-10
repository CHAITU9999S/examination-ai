
import pytest

from app.auth import create_access_token
from app.models import User, QuestionBank, Option


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


def test_examiner_can_create_mcq(client, db_session):
    examiner = create_user(
        db_session,
        "examiner",
        "mcq_examiner@test.com"
    )

    response = client.post(
        "/questions/",
        json={
            "question_text": "What is Python?",
            "question_type": "MCQ",
            "subject": "Programming",
            "difficulty": "Easy",
            "expected_answer": "A programming language",
            "model_answer_text": "Python is a high-level programming language.",
            "marks": 2,
            "negative_marks": 0.5,
            "tags": ["Python", "Programming"],
            "options": ["Programming language", "Operating system"],
            "correct_option_index": 0
        },
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Question created successfully"

    question = db_session.query(QuestionBank).filter(
        QuestionBank.id == response.json()["question_id"]
    ).first()

    assert question is not None
    assert question.expected_answer == "A programming language"
    assert question.model_answer_text == "Python is a high-level programming language."
    assert question.tags == ["Python", "Programming"]

    options = db_session.query(Option).filter(
        Option.question_id == question.id
    ).all()

    assert len(options) == 2
    assert sum(option.is_correct for option in options) == 1


def test_examiner_can_create_multi_select(client, db_session):
    examiner = create_user(
        db_session,
        "examiner",
        "multi_examiner@test.com"
    )

    response = client.post(
        "/questions/",
        json={
            "question_text": "Select programming languages.",
            "question_type": "multi_select",
            "subject": "Programming",
            "difficulty": "Medium",
            "expected_answer": "Python and Java",
            "marks": 3,
            "negative_marks": 1,
            "tags": ["Programming"],
            "options": ["Python", "Java", "HTML"],
            "correct_option_indices": [0, 1]
        },
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 200

    question_id = response.json()["question_id"]

    options = db_session.query(Option).filter(
        Option.question_id == question_id
    ).all()

    assert len(options) == 3
    assert sum(option.is_correct for option in options) == 2


@pytest.mark.parametrize(
    "question_type,question_text",
    [
        ("short_answer", "Define Python."),
        ("long_answer", "Explain object-oriented programming."),
        ("image_upload", "Upload a network diagram.")
    ]
)
def test_examiner_can_create_other_question_types(
    client,
    db_session,
    question_type,
    question_text
):
    examiner = create_user(
        db_session,
        "examiner",
        f"{question_type}_examiner@test.com"
    )

    response = client.post(
        "/questions/",
        json={
            "question_text": question_text,
            "question_type": question_type,
            "subject": "Computer Science",
            "difficulty": "Easy",
            "model_answer_text": "Sample model answer",
            "marks": 5,
            "negative_marks": 0,
            "tags": ["Computer Science"],
            "options": []
        },
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 200

    question = db_session.query(QuestionBank).filter(
        QuestionBank.id == response.json()["question_id"]
    ).first()

    assert question is not None
    assert question.question_type == question_type
    assert question.marks == 5


def test_get_questions_returns_answers_and_options(
    client,
    db_session
):
    examiner = create_user(
        db_session,
        "examiner",
        "get_questions_examiner@test.com"
    )

    create_response = client.post(
        "/questions/",
        json={
            "question_text": "What is 2 + 2?",
            "question_type": "MCQ",
            "subject": "Mathematics",
            "difficulty": "Easy",
            "expected_answer": "4",
            "model_answer_text": "Adding two and two gives four.",
            "marks": 2,
            "negative_marks": 0.5,
            "tags": ["Addition"],
            "options": ["3", "4"],
            "correct_option_index": 1
        },
        headers=get_auth_headers(examiner)
    )

    assert create_response.status_code == 200

    response = client.get(
        "/questions/",
        headers=get_auth_headers(examiner)
    )

    assert response.status_code == 200

    question = next(
        item for item in response.json()
        if item["id"] == create_response.json()["question_id"]
    )

    assert question["expected_answer"] == "4"
    assert question["model_answer_text"] == "Adding two and two gives four."
    assert question["tags"] == ["Addition"]
    assert len(question["options"]) == 2

    correct_options = [
        option for option in question["options"]
        if option["is_correct"]
    ]

    assert len(correct_options) == 1
    assert correct_options[0]["option_text"] == "4"


def test_student_cannot_create_question(client, db_session):
    student = create_user(
        db_session,
        "student",
        "student_create_question@test.com"
    )

    response = client.post(
        "/questions/",
        json={
            "question_text": "What is Python?",
            "question_type": "MCQ",
            "subject": "Programming",
            "difficulty": "Easy",
            "marks": 2,
            "options": ["Language", "OS"],
            "correct_option_index": 0
        },
        headers=get_auth_headers(student)
    )

    assert response.status_code == 403


def test_student_cannot_list_questions(client, db_session):
    student = create_user(
        db_session,
        "student",
        "student_list_questions@test.com"
    )

    response = client.get(
        "/questions/",
        headers=get_auth_headers(student)
    )

    assert response.status_code == 403
  
