import pytest

from app.services.question_validation import validate_question


def test_valid_mcq():
    assert validate_question(
        "MCQ",
        "What is Python?",
        2,
        ["A", "B"],
        correct_option_index=0
    ) is True


def test_rejects_empty_question():
    with pytest.raises(ValueError):
        validate_question("short_answer", "", 2)


def test_rejects_invalid_marks():
    with pytest.raises(ValueError):
        validate_question("short_answer", "Explain Python", 0)


def test_rejects_mcq_without_options():
    with pytest.raises(ValueError):
        validate_question("MCQ", "What is Python?", 2)


def test_rejects_invalid_question_type():
    with pytest.raises(ValueError):
        validate_question("ESSAY", "Explain Python", 5)
