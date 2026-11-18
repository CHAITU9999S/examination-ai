
from datetime import datetime, timedelta, timezone

from app.auth import (
    create_access_token,
    create_exam_access_token,
)
from app.models import (
    User,
    Exam,
    ExamSession,
    ExamQuestion,
    QuestionBank,
    Option,
)


def create_student(
    db,
    email="student@test.com",
    role="student",
    active=True,
):
    student = User(
        full_name="Test Student",
        email=email,
        password_hash="test-hash",
        role=role,
        is_active=active,
    )

    db.add(student)
    db.commit()
    db.refresh(student)

    return student


def create_exam(db, title="Security Test Exam"):
    exam = Exam(
        title=title,
        subject="General Knowledge",
        duration_minutes=30,
        total_questions=1,
        randomize_questions=False,
        start_time=None,
        end_time=None,
        created_by=None,
    )

    db.add(exam)
    db.commit()
    db.refresh(exam)

    return exam


def create_active_session(
    db,
    exam,
    student,
    selected_question_ids=None,
):
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now,
        expires_at=now + timedelta(
            minutes=exam.duration_minutes
        ),
        status="in_progress",
        selected_question_ids=selected_question_ids,
    )

    db.add(session)
    db.commit()
    db.refresh(session)

    return session


def create_exam_token(exam, student, session):
    return create_exam_access_token(
        exam_id=exam.id,
        student_id=student.id,
        session_id=session.id,
        expires_at=session.expires_at,
    )


def test_normal_access_token_rejected_for_exam_paper(
    client,
    db_session,
):
    student = create_student(db_session)
    exam = create_exam(db_session)

    create_active_session(
        db_session,
        exam,
        student,
    )

    token = create_access_token({
        "sub": str(student.id)
    })

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 401


def test_exam_token_rejected_for_wrong_exam(
    client,
    db_session,
):
    student = create_student(db_session)
    exam = create_exam(db_session)

    session = create_active_session(
        db_session,
        exam,
        student,
    )

    token = create_exam_token(
        exam,
        student,
        session,
    )

    response = client.get(
        f"/exam-sessions/paper/{exam.id + 1}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403


def test_inactive_student_cannot_access_exam(
    client,
    db_session,
):
    student = create_student(
        db_session,
        active=False,
    )

    exam = create_exam(db_session)

    session = create_active_session(
        db_session,
        exam,
        student,
    )

    token = create_exam_token(
        exam,
        student,
        session,
    )

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403


def test_non_student_cannot_access_exam(
    client,
    db_session,
):
    examiner = create_student(
        db_session,
        email="examiner@test.com",
        role="examiner",
    )

    exam = create_exam(db_session)

    session = create_active_session(
        db_session,
        exam,
        examiner,
    )

    token = create_exam_token(
        exam,
        examiner,
        session,
    )

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403


def test_exam_access_requires_existing_session(
    client,
    db_session,
):
    student = create_student(db_session)
    exam = create_exam(db_session)

    token = create_exam_access_token(
        exam_id=exam.id,
        student_id=student.id,
        session_id=999999,
        expires_at=(
            datetime.now(timezone.utc)
            + timedelta(minutes=30)
        ),
    )

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 403


def test_valid_student_can_access_assigned_exam_paper(
    client,
    db_session,
):
    student = create_student(db_session)
    exam = create_exam(db_session)

    question = QuestionBank(
        question_text="What is the capital of India?",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=2,
        negative_marks=0.5,
    )

    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    # Assign the question to the examination.
    exam_question = ExamQuestion(
        exam_id=exam.id,
        question_id=question.id,
        question_order=1,
    )

    db_session.add(exam_question)
    db_session.commit()

    option = Option(
        question_id=question.id,
        option_text="New Delhi",
        is_correct=True,
    )

    db_session.add(option)
    db_session.commit()

    # Save the selected question IDs in the session.
    session = create_active_session(
        db_session,
        exam,
        student,
        selected_question_ids=[question.id],
    )

    token = create_exam_token(
        exam,
        student,
        session,
    )

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={
            "Authorization": f"Bearer {token}"
        },
    )

    assert response.status_code == 200

    data = response.json()

    assert data["exam_id"] == exam.id
    assert data["session_id"] == session.id
    assert data["total_questions"] == 1

    assert len(data["questions"]) == 1

    returned_question = data["questions"][0]

    assert returned_question["question_id"] == question.id

    assert (
        returned_question["question_text"]
        == "What is the capital of India?"
    )

    assert len(returned_question["options"]) == 1

    returned_option = returned_question["options"][0]

    assert returned_option["option_text"] == "New Delhi"

    # Correct answers must never be exposed to students.
    assert "is_correct" not in returned_option
    
