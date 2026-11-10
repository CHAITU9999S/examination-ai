import pytest

from app.services.question_validation import validate_question


def test_valid_mcq():
    assert validate_question(
        "MCQ", "What is Python?", 2,
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

def test_rejects_negative_mcq_index():
    with pytest.raises(ValueError):
        validate_question(
            "MCQ", "What is Python?", 2,
            ["A", "B"],
            correct_option_index=-1
        )


def test_valid_multi_select():
    assert validate_question(
        "multi_select",
        "Select programming languages",
        2,
        ["Python", "Java", "HTML"],
        correct_option_indices=[0, 1]
    ) is True


def test_rejects_multi_select_without_correct_options():
    with pytest.raises(ValueError):
        validate_question(
            "multi_select",
            "Select programming languages",
            2,
            ["Python", "Java"]
        )


def test_rejects_invalid_multi_select_index():
    with pytest.raises(ValueError):
        validate_question(
            "multi_select",
            "Select programming languages",
            2,
            ["Python", "Java"],
            correct_option_indices=[0, 5]
    )
