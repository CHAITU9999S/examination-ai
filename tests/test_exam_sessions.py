
from app.auth import create_access_token, create_exam_access_token
from app.models import User, Exam, ExamSession, QuestionBank, Option


def create_student(db, email="student@test.com", role="student", active=True):
    student = User(
        full_name="Test Student",
        email=email,
        password_hash="test-hash",
        role=role,
        is_active=active
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
        created_by=None
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


def create_active_session(db, exam, student):
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="in_progress"
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def test_normal_access_token_rejected_for_exam_paper(client, db_session):
    student = create_student(db_session)
    exam = create_exam(db_session)
    create_active_session(db_session, exam, student)

    token = create_access_token({"sub": str(student.id)})

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 401


def test_exam_token_rejected_for_wrong_exam(client, db_session):
    student = create_student(db_session)
    exam = create_exam(db_session)

    token = create_exam_access_token(
        exam_id=exam.id,
        student_id=student.id
    )

    response = client.get(
        f"/exam-sessions/paper/{exam.id + 1}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_exam_token_identity_mismatch_rejected(client, db_session):
    student = create_student(db_session)


    # Create a token whose subject does not match student_id.
    from app.auth import create_access_token

    mismatched_token = create_access_token({
        "sub": str(student.id + 100),
        "exam_id": 10,
        "student_id": student.id,
        "token_type": "exam"
    })

    response = client.get(
        "/exam-sessions/paper/10",
        headers={"Authorization": f"Bearer {mismatched_token}"}
    )

    assert response.status_code == 401


def test_inactive_student_cannot_access_exam(client, db_session):
    student = create_student(
        db_session,
        active=False
    )
    exam = create_exam(db_session)
    create_active_session(db_session, exam, student)

    token = create_exam_access_token(exam.id, student.id)

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_non_student_cannot_access_exam(client, db_session):
    examiner = create_student(
        db_session,
        email="examiner@test.com",
        role="examiner"
    )
    exam = create_exam(db_session)
    create_active_session(db_session, exam, examiner)

    token = create_exam_access_token(exam.id, examiner.id)

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_exam_access_requires_active_session(client, db_session):
    student = create_student(db_session)
    exam = create_exam(db_session)

    token = create_exam_access_token(exam.id, student.id)

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


def test_valid_student_can_access_exam_paper(client, db_session):
    student = create_student(db_session)
    exam = create_exam(db_session)
    create_active_session(db_session, exam, student)

    question = QuestionBank(
        question_text="What is the capital of India?",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="Easy",
        marks=2,
        negative_marks=0.5
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    option = Option(
        question_id=question.id,
        option_text="New Delhi",
        is_correct=True
    )
    db_session.add(option)
    db_session.commit()

    token = create_exam_access_token(exam.id, student.id)

    response = client.get(
        f"/exam-sessions/paper/{exam.id}",
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200

    data = response.json()

    assert data["exam_id"] == exam.id
    assert data["total_questions"] == 1
    assert len(data["questions"]) == 1
    assert data["questions"][0]["question_text"] == "What is the capital of India?"

    # Correct answers must never be exposed to students.
    assert "is_correct" not in data["questions"][0]["options"][0]
      
