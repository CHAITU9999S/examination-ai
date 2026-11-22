
from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas import QuestionCreate, ExamCreate


def valid_exam_data():
    now = datetime.now(timezone.utc)

    return {
        "title": "Python Test",
        "subject": "Programming",
        "duration_minutes": 60,
        "total_questions": 20,
        "randomize_questions": True,
        "start_time": now + timedelta(days=1),
        "end_time": now + timedelta(days=2),
        "negative_marking": True,
        "proctoring_enabled": True,
    }


def test_valid_question():
    question = QuestionCreate(
        question_text="What is Python?",
        question_type="MCQ",
        subject="Programming",
        difficulty="easy",
        marks=2,
        options=["Option A", "Option B"],
        correct_option_index=0,
    )

    assert question.marks == 2
    assert len(question.options) == 2


def test_question_schema_accepts_image_only_prompt():
    question = QuestionCreate(
        question_text=None,
        question_type="short_answer",
        subject="Programming",
        difficulty="easy",
        marks=2,
    )

    assert question.question_text is None


def test_question_rejects_zero_marks():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="easy",
            marks=0,
        )


def test_valid_exam():
    exam = ExamCreate(**valid_exam_data())

    assert exam.duration_minutes == 60
    assert exam.total_questions == 20


def test_exam_rejects_zero_duration():
    data = valid_exam_data()
    data["duration_minutes"] = 0

    with pytest.raises(ValidationError):
        ExamCreate(**data)


def test_valid_multi_select_question():
    question = QuestionCreate(
        question_text="Select programming languages",
        question_type="multi_select",
        subject="Programming",
        difficulty="easy",
        marks=2,
        options=["Python", "Java", "HTML"],
        correct_option_indices=[0, 1],
    )

    assert question.correct_option_indices == [0, 1]


def test_question_rejects_negative_marks():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="easy",
            marks=2,
            negative_marks=-1,
        )


def test_question_rejects_invalid_difficulty():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="Very Easy",
            marks=2,
        )


def test_exam_rejects_negative_total_questions():
    data = valid_exam_data()
    data["total_questions"] = -1

    with pytest.raises(ValidationError):
        ExamCreate(**data)


def test_question_rejects_negative_correct_option_index():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="easy",
            marks=2,
            options=["A", "B"],
            correct_option_index=-1,
        )


def test_question_accepts_all_supported_question_types():
    question_types = [
        "MCQ",
        "multi_select",
        "short_answer",
        "long_answer",
        "image_upload",
    ]

    for question_type in question_types:
        question = QuestionCreate(
            question_text="Test question",
            question_type=question_type,
            subject="Programming",
            difficulty="medium",
            marks=5,
        )

        assert question.question_type.value == question_type


def test_question_rejects_invalid_question_type():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="essay",
            subject="Programming",
            difficulty="easy",
            marks=5,
        )


def test_question_accepts_zero_negative_marks():
    question = QuestionCreate(
        question_text="Test question",
        question_type="short_answer",
        subject="Programming",
        difficulty="easy",
        marks=5,
        negative_marks=0,
    )

    assert question.negative_marks == 0


def test_exam_rejects_negative_tab_switch_warnings():
    data = valid_exam_data()
    data["max_tab_switch_warnings"] = -1

    with pytest.raises(ValidationError):
        ExamCreate(**data)


def test_exam_rejects_invalid_gaze_sensitivity():
    data = valid_exam_data()
    data["gaze_tracking_sensitivity"] = 1.5

    with pytest.raises(ValidationError):
        ExamCreate(**data)


def test_exam_rejects_missing_start_time():
    data = valid_exam_data()
    del data["start_time"]

    with pytest.raises(ValidationError):
        ExamCreate(**data)


def test_exam_rejects_missing_end_time():
    data = valid_exam_data()
    del data["end_time"]

    with pytest.raises(ValidationError):
        ExamCreate(**data)
