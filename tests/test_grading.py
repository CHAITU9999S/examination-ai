from datetime import datetime, timedelta, timezone

import pytest

from app.auth import create_access_token
from app.models import Answer, Exam, ExamSession, QuestionBank, Result, User


@pytest.fixture
def grading_data(db_session):
    examiner = User(
        full_name="Grading Examiner",
        email="grading-examiner@example.com",
        password_hash="test-password-hash",
        role="examiner",
        is_active=True,
    )
    student = User(
        full_name="Grading Student",
        email="grading-student@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )
    db_session.add_all([examiner, student])
    db_session.commit()
    db_session.refresh(examiner)
    db_session.refresh(student)

    exam = Exam(
        title="Subjective Grading Test",
        subject="Computer Science",
        duration_minutes=30,
        total_questions=1,
        negative_marking=False,
        proctoring_enabled=False,
        created_by=examiner.id,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    question = QuestionBank(
        question_text="Explain a database.",
        question_type="short_answer",
        subject="Computer Science",
        difficulty="easy",
        marks=5,
        negative_marks=0,
        expected_answer="A database is an organized collection of data.",
        model_answer_text="A database stores and organizes related information.",
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now - timedelta(minutes=20),
        submitted_at=now,
        expires_at=now - timedelta(minutes=1),
        status="submitted",
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="A database stores organized information.",
    )
    db_session.add(answer)
    db_session.commit()
    db_session.refresh(answer)

    return {
        "examiner": examiner,
        "student": student,
        "exam": exam,
        "question": question,
        "session": session,
        "answer": answer,
    }


def auth_headers(user):
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_examiner_can_manually_grade_subjective_answer(
    client,
    db_session,
    grading_data,
):
    data = grading_data

    response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={"awarded_marks": 4.0},
    )

    assert response.status_code == 200
    assert response.json()["awarded_marks"] == pytest.approx(4.0)
    assert response.json()["result_ready"] is True

    saved_answer = db_session.query(Answer).filter(
        Answer.id == data["answer"].id,
    ).first()
    saved_result = db_session.query(Result).filter(
        Result.session_id == data["session"].id,
    ).first()

    assert saved_answer.awarded_marks == pytest.approx(4.0)
    assert saved_result.total_marks == pytest.approx(5.0)
    assert saved_result.obtained_marks == pytest.approx(4.0)
    assert saved_result.percentage == pytest.approx(80.0)


def test_ai_grading_is_disabled_without_explicit_opt_in(
    client,
    grading_data,
    monkeypatch,
):
    data = grading_data

    monkeypatch.setenv("AI_GRADING_ENABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


def test_student_cannot_manually_grade_subjective_answer(
    client,
    grading_data,
):
    data = grading_data

    response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["student"]),
        json={"awarded_marks": 4.0},
    )

    assert response.status_code == 403
