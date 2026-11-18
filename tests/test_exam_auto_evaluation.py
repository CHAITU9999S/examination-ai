import json
from datetime import datetime, timedelta, timezone

from app.models import (
    Answer,
    Exam,
    ExamQuestion,
    ExamSession,
    Option,
    QuestionBank,
    Result,
    User,
)
from app.services.exam_scheduler import submit_expired_exam_sessions


def test_scheduler_submits_and_evaluates_expired_exam(
    db_session,
    monkeypatch,
):
    student = User(
        full_name="Auto Evaluation Student",
        email="auto-evaluation-student@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    exam = Exam(
        title="Automatic Submission Test",
        subject="Computer Science",
        duration_minutes=1,
        total_questions=1,
        randomize_questions=False,
        negative_marking=True,
        proctoring_enabled=False,
        created_by=None,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    question = QuestionBank(
        question_text="Which language is Python?",
        question_type="MCQ",
        subject="Computer Science",
        difficulty="easy",
        marks=2,
        negative_marks=0.5,
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

    correct_option = Option(
        question_id=question.id,
        option_text="A programming language",
        is_correct=True,
    )
    db_session.add(correct_option)
    db_session.commit()
    db_session.refresh(correct_option)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now - timedelta(minutes=2),
        expires_at=now - timedelta(seconds=30),
        submitted_at=None,
        status="in_progress",
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    db_session.add(
        Answer(
            session_id=session.id,
            question_id=question.id,
            answer_text=json.dumps([correct_option.id]),
        )
    )
    db_session.commit()

    monkeypatch.setattr(
        "app.services.exam_scheduler.SessionLocal",
        lambda: db_session,
    )

    submit_expired_exam_sessions()

    db_session.expire_all()

    saved_session = db_session.query(ExamSession).filter(
        ExamSession.id == session.id,
    ).first()
    saved_result = db_session.query(Result).filter(
        Result.session_id == session.id,
    ).first()

    assert saved_session.status == "submitted"
    assert saved_session.submitted_at is not None
    assert saved_result is not None
    assert saved_result.total_marks == 2
    assert saved_result.obtained_marks == 2
    assert saved_result.percentage == 100
