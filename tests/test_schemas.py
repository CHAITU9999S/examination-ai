import pytest
from pydantic import ValidationError

from app.schemas import QuestionCreate, ExamCreate


def test_valid_question():
    question = QuestionCreate(
        question_text="What is Python?",
        question_type="MCQ",
        subject="Programming",
        difficulty="Easy",
        marks=2,
        options=["Option A", "Option B"]
    )

    assert question.marks == 2
    assert len(question.options) == 2


def test_question_rejects_zero_marks():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="Easy",
            marks=0
        )


def test_valid_exam():
    exam = ExamCreate(
        title="Python Test",
        subject="Programming",
        duration_minutes=60
    )

    assert exam.duration_minutes == 60


def test_exam_rejects_zero_duration():
    with pytest.raises(ValidationError):
        ExamCreate(
            title="Python Test",
            subject="Programming",
            duration_minutes=0
)

def test_valid_multi_select_question():
    question = QuestionCreate(
        question_text="Select programming languages",
        question_type="multi_select",
        subject="Programming",
        difficulty="Easy",
        marks=2,
        options=["Python", "Java", "HTML"],
        correct_option_indices=[0, 1]
    )

    assert question.correct_option_indices == [0, 1]


def test_question_rejects_negative_marks():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="Easy",
            marks=2,
            negative_marks=-1
        )


def test_question_rejects_invalid_difficulty():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="Very Easy",
            marks=2
        )


def test_exam_rejects_negative_total_questions():
    with pytest.raises(ValidationError):
        ExamCreate(
            title="Python Test",
            subject="Programming",
            duration_minutes=60,
            total_questions=-1
        )


def test_question_rejects_negative_correct_option_index():
    with pytest.raises(ValidationError):
        QuestionCreate(
            question_text="Test question",
            question_type="MCQ",
            subject="Programming",
            difficulty="Easy",
            marks=2,
            options=["A", "B"],
            correct_option_index=-1
        )
