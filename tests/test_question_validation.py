import pytest

from app.services.question_validation import validate_question


def test_valid_mcq():
    assert validate_question(
        "MCQ", "What is Python?", 2,
        ["A", "B"]
    ) is True


def test_rejects_empty_question():
    with pytest.raises(ValueError):
        validate_question("SHORT", "", 2)


def test_rejects_invalid_marks():
    with pytest.raises(ValueError):
        validate_question("SHORT", "Explain Python", 0)


def test_rejects_mcq_without_options():
    with pytest.raises(ValueError):
        validate_question("MCQ", "What is Python?", 2)


def test_rejects_invalid_question_type():
    with pytest.raises(ValueError):
        validate_question("ESSAY", "Explain Python", 5)
