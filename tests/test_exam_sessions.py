
from datetime import datetime, timedelta, timezone

from app.auth import (
    create_access_token,
    create_exam_access_token,
    verify_token,
)
from app.services.session_service import get_or_create_session_question_ids
from app.models import (
    User,
    Exam,
    ExamSession,
    ExamAssignment,
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
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam = Exam(
        title=title,
        subject="General Knowledge",
        duration_minutes=30,
        total_questions=1,
        randomize_questions=False,
        start_time=now - timedelta(minutes=1),
        end_time=now + timedelta(hours=2),
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

    if student.role == "student":
        assignment = db.query(ExamAssignment).filter(
            ExamAssignment.exam_id == exam.id,
            ExamAssignment.student_id == student.id,
        ).first()
        if assignment is None:
            db.add(ExamAssignment(
                exam_id=exam.id,
                student_id=student.id,
                assigned_by=student.id,
                is_active=True,
            ))
            db.commit()

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
    assert data["exam_title"] == exam.title
    assert data["duration_minutes"] == exam.duration_minutes
    assert data["session_id"] == session.id
    assert data["total_questions"] == 1

    assert len(data["questions"]) == 1

    returned_question = data["questions"][0]

    assert returned_question["id"] == question.id
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
    


def test_saved_question_selection_uses_filtered_pool_when_total_is_unset(
    db_session,
):
    student = create_student(
        db_session,
        email="filtered-paper-student@test.com",
    )

    exam = Exam(
        title="Filtered Question Pool",
        subject="General Knowledge",
        duration_minutes=30,
        total_questions=None,
        randomize_questions=False,
        selection_rules={"difficulty": "easy"},
        created_by=None,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    easy_questions = [
        QuestionBank(
            question_text=f"Easy question {index}",
            question_type="MCQ",
            subject="General Knowledge",
            difficulty="easy",
            marks=1,
            negative_marks=0,
        )
        for index in range(1, 3)
    ]
    hard_question = QuestionBank(
        question_text="Hard question",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="hard",
        marks=1,
        negative_marks=0,
    )
    db_session.add_all([*easy_questions, hard_question])
    db_session.commit()

    for question in [*easy_questions, hard_question]:
        db_session.add(
            ExamQuestion(
                exam_id=exam.id,
                question_id=question.id,
            )
        )
    db_session.commit()

    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=(
            datetime.now(timezone.utc).replace(tzinfo=None)
            + timedelta(minutes=30)
        ),
        status="in_progress",
        selected_question_ids=None,
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    selected_ids = get_or_create_session_question_ids(
        session,
        exam,
        db_session,
    )

    assert len(selected_ids) == 2
    assert set(selected_ids) == {
        question.id for question in easy_questions
    }

def test_student_starts_exam_using_exam_id_path(
    client,
    db_session,
):
    student = create_student(
        db_session,
        email="start-exam-contract@test.com",
    )
    exam = create_exam(db_session, title="Start Contract Exam")
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=student.id,
        is_active=True,
    ))
    db_session.commit()
    question = QuestionBank(
        question_text="A sample question",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=1,
        negative_marks=0,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    db_session.add(
        ExamQuestion(
            exam_id=exam.id,
            question_id=question.id,
            question_order=1,
        )
    )
    db_session.commit()

    access_token = create_access_token({"sub": str(student.id)})
    response = client.post(
        f"/exam-sessions/start/{exam.id}",
        headers={"Authorization": f"Bearer {access_token}"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["exam_id"] == exam.id
    assert data["session_id"] > 0
    assert data["access_token"]
    assert data["token_type"] == "bearer"
    assert data["total_questions"] == 1

def test_exam_access_tokens_are_short_lived_and_refresh_tokens_rotate(
    client,
    db_session,
):
    student = create_student(
        db_session,
        email="rotating-token-student@test.com",
    )
    exam = create_exam(
        db_session,
        title="Rotating Token Exam",
    )
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=student.id,
        is_active=True,
    ))
    db_session.commit()
    question = QuestionBank(
        question_text="A token refresh question",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=1,
        negative_marks=0,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    db_session.add(
        ExamQuestion(
            exam_id=exam.id,
            question_id=question.id,
            question_order=1,
        )
    )
    db_session.commit()

    login_token = create_access_token({"sub": str(student.id)})
    start_response = client.post(
        f"/exam-sessions/start/{exam.id}",
        headers={"Authorization": f"Bearer {login_token}"},
    )

    assert start_response.status_code == 200
    started = start_response.json()
    assert started["refresh_token"]

    session = db_session.query(ExamSession).filter_by(
        id=started["session_id"],
    ).one()
    assert session.exam_token_refresh_hash
    assert session.exam_token_refresh_hash != started["refresh_token"]

    first_claims = verify_token(
        started["access_token"],
        expected_token_type="exam",
    )
    assert first_claims is not None
    assert first_claims["exp"] <= first_claims["iat"] + 600

    refresh_url = f"/exam-sessions/refresh/{started['session_id']}"
    refresh_response = client.post(
        refresh_url,
        json={"refresh_token": started["refresh_token"]},
    )

    assert refresh_response.status_code == 200
    refreshed = refresh_response.json()
    assert refreshed["access_token"] != started["access_token"]
    assert refreshed["refresh_token"] != started["refresh_token"]

    replay_response = client.post(
        refresh_url,
        json={"refresh_token": started["refresh_token"]},
    )
    assert replay_response.status_code == 401

    second_refresh_response = client.post(
        refresh_url,
        json={"refresh_token": refreshed["refresh_token"]},
    )
    assert second_refresh_response.status_code == 200

def test_exam_refresh_rejects_inactive_student(
    client,
    db_session,
):
    student = create_student(
        db_session,
        email="inactive-refresh-student@test.com",
    )
    exam = create_exam(
        db_session,
        title="Inactive Refresh Exam",
    )
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=student.id,
        is_active=True,
    ))
    db_session.commit()
    question = QuestionBank(
        question_text="A refresh authorization question",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=1,
        negative_marks=0,
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)
    db_session.add(
        ExamQuestion(
            exam_id=exam.id,
            question_id=question.id,
            question_order=1,
        )
    )
    db_session.commit()

    login_token = create_access_token({"sub": str(student.id)})
    start_response = client.post(
        f"/exam-sessions/start/{exam.id}",
        headers={"Authorization": f"Bearer {login_token}"},
    )
    assert start_response.status_code == 200
    started = start_response.json()

    student.is_active = False
    db_session.commit()

    refresh_response = client.post(
        f"/exam-sessions/refresh/{started['session_id']}",
        json={"refresh_token": started["refresh_token"]},
    )
    assert refresh_response.status_code == 403



def test_student_cannot_start_exam_before_opening_time(client, db_session):
    student = create_student(db_session, email="early-start@test.com")
    exam = create_exam(db_session, title="Not Open Yet")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam.start_time = now + timedelta(hours=1)
    exam.end_time = now + timedelta(hours=2)
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=student.id,
        is_active=True,
    ))
    db_session.commit()

    response = client.post(
        f"/exam-sessions/start/{exam.id}",
        headers={"Authorization": f"Bearer {create_access_token(str(student.id))}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Exam has not started yet."


def test_student_cannot_start_exam_after_closing_time(client, db_session):
    student = create_student(db_session, email="late-start@test.com")
    exam = create_exam(db_session, title="Already Closed")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam.start_time = now - timedelta(hours=2)
    exam.end_time = now - timedelta(hours=1)
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=student.id,
        is_active=True,
    ))
    db_session.commit()

    response = client.post(
        f"/exam-sessions/start/{exam.id}",
        headers={"Authorization": f"Bearer {create_access_token(str(student.id))}"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Exam schedule has ended."


def test_student_can_pause_and_resume_exam_session(client, db_session):
    student = create_student(db_session, email="pause-resume@test.com")
    exam = create_exam(db_session, title="Pause and Resume")
    session = create_active_session(db_session, exam, student)
    token = create_exam_token(exam, student, session)
    original_expiry = session.expires_at

    pause_response = client.post(
        f"/exam-sessions/pause/{session.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert pause_response.status_code == 200
    assert pause_response.json()["is_paused"] is True
    db_session.refresh(session)
    assert session.is_paused is True
    assert session.expires_at == original_expiry

    resume_response = client.post(
        f"/exam-sessions/resume/{session.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["is_paused"] is False
    db_session.refresh(session)
    assert session.is_paused is False
    assert session.expires_at == original_expiry


def test_expired_exam_session_is_submitted_automatically(client, db_session):
    student = create_student(db_session, email="auto-submit@test.com")
    exam = create_exam(db_session, title="Auto Submit")
    session = create_active_session(db_session, exam, student)
    token = create_exam_token(exam, student, session)
    session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
    db_session.commit()

    response = client.post(
        f"/exam-sessions/submit/{session.id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    db_session.refresh(session)
    assert session.status == "submitted"
    assert session.submitted_at is not None
