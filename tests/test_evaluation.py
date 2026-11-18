
import json
from datetime import datetime, timedelta, timezone

import pytest

from app.models import (
    User,
    Exam,
    ExamSession,
    ExamQuestion,
    QuestionBank,
    Option,
    Answer,
    Result,
)

from app.services.evaluation_service import (
    evaluate_objective_answer,
    evaluate_objective_answers,
    calculate_session_result,
    evaluate_exam_session,
)


@pytest.fixture
def evaluation_data(db_session):
    """Create an examination with objective and subjective questions."""

    student = User(
        full_name="Evaluation Student",
        email="evaluationstudent@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )

    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    exam = Exam(
        title="Evaluation Test Exam",
        subject="General Knowledge",
        duration_minutes=30,
        total_questions=3,
        randomize_questions=False,
        negative_marking=True,
        start_time=None,
        end_time=None,
        created_by=None,
    )

    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    mcq = QuestionBank(
        question_text="What is the capital of India?",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=2,
        negative_marks=0.5,
    )

    multi_select = QuestionBank(
        question_text="Select the programming languages.",
        question_type="multi_select",
        subject="Programming",
        difficulty="medium",
        marks=3,
        negative_marks=1,
    )

    subjective = QuestionBank(
        question_text="Explain a database.",
        question_type="short_answer",
        subject="Computer Science",
        difficulty="easy",
        marks=5,
        negative_marks=0,
        expected_answer="A database is an organized collection of data.",
    )

    db_session.add_all([
        mcq,
        multi_select,
        subjective,
    ])

    db_session.commit()

    for question in (mcq, multi_select, subjective):
        db_session.refresh(question)

        db_session.add(
            ExamQuestion(
                exam_id=exam.id,
                question_id=question.id,
            )
        )

    db_session.commit()

    mcq_correct = Option(
        question_id=mcq.id,
        option_text="New Delhi",
        is_correct=True,
    )

    mcq_wrong = Option(
        question_id=mcq.id,
        option_text="Mumbai",
        is_correct=False,
    )

    multi_correct_one = Option(
        question_id=multi_select.id,
        option_text="Python",
        is_correct=True,
    )

    multi_correct_two = Option(
        question_id=multi_select.id,
        option_text="Java",
        is_correct=True,
    )

    multi_wrong = Option(
        question_id=multi_select.id,
        option_text="HTML",
        is_correct=False,
    )

    db_session.add_all([
        mcq_correct,
        mcq_wrong,
        multi_correct_one,
        multi_correct_two,
        multi_wrong,
    ])

    db_session.commit()

    for option in (
        mcq_correct,
        mcq_wrong,
        multi_correct_one,
        multi_correct_two,
        multi_wrong,
    ):
        db_session.refresh(option)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now - timedelta(minutes=20),
        expires_at=now - timedelta(minutes=1),
        submitted_at=now,
        status="submitted",
        selected_question_ids=[
            mcq.id,
            multi_select.id,
            subjective.id,
        ],
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    return {
        "student": student,
        "exam": exam,
        "session": session,
        "mcq": mcq,
        "multi_select": multi_select,
        "subjective": subjective,
        "mcq_correct": mcq_correct,
        "mcq_wrong": mcq_wrong,
        "multi_correct_one": multi_correct_one,
        "multi_correct_two": multi_correct_two,
        "multi_wrong": multi_wrong,
    }


def create_answer(db, session, question, option_ids=None, text=None):
    """Create an answer using the stored JSON option-ID format."""

    if option_ids is not None:
        answer_text = json.dumps(option_ids)
    else:
        answer_text = text

    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text=answer_text,
    )

    db.add(answer)
    db.commit()
    db.refresh(answer)

    return answer


def test_correct_mcq_answer_receives_full_marks(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    answer = create_answer(
        db_session,
        data["session"],
        data["mcq"],
        option_ids=[data["mcq_correct"].id],
    )

    marks = evaluate_objective_answer(
        db_session,
        data["mcq"],
        answer,
    )

    assert marks == pytest.approx(2.0)


def test_wrong_mcq_answer_receives_negative_marks(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    answer = create_answer(
        db_session,
        data["session"],
        data["mcq"],
        option_ids=[data["mcq_wrong"].id],
    )

    marks = evaluate_objective_answer(
        db_session,
        data["mcq"],
        answer,
    )

    assert marks == pytest.approx(-0.5)


def test_unanswered_mcq_receives_zero_marks(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    marks = evaluate_objective_answer(
        db_session,
        data["mcq"],
        None,
    )

    assert marks == pytest.approx(0.0)


def test_correct_multi_select_answer_receives_full_marks(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    answer = create_answer(
        db_session,
        data["session"],
        data["multi_select"],
        option_ids=[
            data["multi_correct_one"].id,
            data["multi_correct_two"].id,
        ],
    )

    marks = evaluate_objective_answer(
        db_session,
        data["multi_select"],
        answer,
    )

    assert marks == pytest.approx(3.0)


def test_incorrect_multi_select_answer_receives_negative_marks(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    answer = create_answer(
        db_session,
        data["session"],
        data["multi_select"],
        option_ids=[
            data["multi_correct_one"].id,
            data["multi_wrong"].id,
        ],
    )

    marks = evaluate_objective_answer(
        db_session,
        data["multi_select"],
        answer,
    )

    assert marks == pytest.approx(-1.0)


def test_invalid_objective_answer_format_is_not_awarded_full_marks(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    answer = create_answer(
        db_session,
        data["session"],
        data["mcq"],
        text="not-valid-json",
    )

    marks = evaluate_objective_answer(
        db_session,
        data["mcq"],
        answer,
    )

    assert marks != pytest.approx(2.0)


def test_objective_evaluation_saves_awarded_marks(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    create_answer(
        db_session,
        data["session"],
        data["mcq"],
        option_ids=[data["mcq_correct"].id],
    )

    create_answer(
        db_session,
        data["session"],
        data["multi_select"],
        option_ids=[
            data["multi_correct_one"].id,
            data["multi_correct_two"].id,
        ],
    )

    evaluate_objective_answers(
        db_session,
        data["session"].id,
    )

    db_session.expire_all()

    mcq_answer = db_session.query(Answer).filter_by(
        session_id=data["session"].id,
        question_id=data["mcq"].id,
    ).first()

    multi_answer = db_session.query(Answer).filter_by(
        session_id=data["session"].id,
        question_id=data["multi_select"].id,
    ).first()

    assert mcq_answer.awarded_marks == pytest.approx(2.0)
    assert multi_answer.awarded_marks == pytest.approx(3.0)


def test_result_calculation_waits_for_subjective_grading(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    create_answer(
        db_session,
        data["session"],
        data["mcq"],
        option_ids=[data["mcq_correct"].id],
    )

    create_answer(
        db_session,
        data["session"],
        data["multi_select"],
        option_ids=[
            data["multi_correct_one"].id,
            data["multi_correct_two"].id,
        ],
    )

    create_answer(
        db_session,
        data["session"],
        data["subjective"],
        text="A database stores organized information.",
    )

    evaluate_objective_answers(
        db_session,
        data["session"].id,
    )

    result_status = calculate_session_result(
        db_session,
        data["session"].id,
    )

    assert result_status["status"] == "pending"
    assert result_status["pending_answers"] == 1

    saved_result = db_session.query(Result).filter_by(
        session_id=data["session"].id,
    ).first()

    assert saved_result is None


def test_result_is_calculated_after_subjective_grading(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    create_answer(
        db_session,
        data["session"],
        data["mcq"],
        option_ids=[data["mcq_correct"].id],
    )

    create_answer(
        db_session,
        data["session"],
        data["multi_select"],
        option_ids=[
            data["multi_correct_one"].id,
            data["multi_correct_two"].id,
        ],
    )

    subjective_answer = create_answer(
        db_session,
        data["session"],
        data["subjective"],
        text="A database stores organized information.",
    )

    evaluate_objective_answers(
        db_session,
        data["session"].id,
    )

    subjective_answer.awarded_marks = 4.0
    db_session.commit()

    result_status = calculate_session_result(
        db_session,
        data["session"].id,
    )

    assert result_status["status"] == "evaluated"

    saved_result = db_session.query(Result).filter_by(
        session_id=data["session"].id,
    ).first()

    assert saved_result is not None
    assert saved_result.total_marks == pytest.approx(10.0)
    assert saved_result.obtained_marks == pytest.approx(9.0)
    assert saved_result.percentage == pytest.approx(90.0)


def test_unanswered_objective_question_receives_zero(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    create_answer(
        db_session,
        data["session"],
        data["multi_select"],
        option_ids=[
            data["multi_correct_one"].id,
            data["multi_correct_two"].id,
        ],
    )

    create_answer(
        db_session,
        data["session"],
        data["subjective"],
        text="A database stores organized information.",
    )

    evaluate_objective_answers(
        db_session,
        data["session"].id,
    )

    subjective_answer = db_session.query(Answer).filter_by(
        session_id=data["session"].id,
        question_id=data["subjective"].id,
    ).first()

    subjective_answer.awarded_marks = 3.0
    db_session.commit()

    result_status = calculate_session_result(
        db_session,
        data["session"].id,
    )

    assert result_status["status"] == "evaluated"

    saved_result = db_session.query(Result).filter_by(
        session_id=data["session"].id,
    ).first()

    assert saved_result.obtained_marks == pytest.approx(6.0)


def test_evaluation_rejects_unsubmitted_session(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    data["session"].status = "in_progress"
    db_session.commit()

    with pytest.raises(ValueError):
        calculate_session_result(
            db_session,
            data["session"].id,
        )


def test_full_evaluation_workflow(
    db_session,
    evaluation_data,
):
    data = evaluation_data

    create_answer(
        db_session,
        data["session"],
        data["mcq"],
        option_ids=[data["mcq_correct"].id],
    )

    create_answer(
        db_session,
        data["session"],
        data["multi_select"],
        option_ids=[
            data["multi_correct_one"].id,
            data["multi_correct_two"].id,
        ],
    )

    create_answer(
        db_session,
        data["session"],
        data["subjective"],
        text="A database stores organized information.",
    )

    workflow = evaluate_exam_session(
        db_session,
        data["session"].id,
    )

    assert "objective_evaluation" in workflow
    assert "result" in workflow
    assert workflow["result"]["status"] == "pending"
