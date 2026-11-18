import math

import pytest

from app.services.question_validation import validate_question


def test_valid_mcq():
    assert validate_question(
        "MCQ",
        "What is Python?",
        2,
        ["A", "B"],
        correct_option_index=0,
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
            "MCQ",
            "What is Python?",
            2,
            ["A", "B"],
            correct_option_index=-1,
        )


def test_valid_multi_select():
    assert validate_question(
        "multi_select",
        "Select programming languages",
        2,
        ["Python", "Java", "HTML"],
        correct_option_indices=[0, 1],
    ) is True


def test_rejects_multi_select_without_correct_options():
    with pytest.raises(ValueError):
        validate_question(
            "multi_select",
            "Select programming languages",
            2,
            ["Python", "Java"],
        )


def test_rejects_invalid_multi_select_index():
    with pytest.raises(ValueError):
        validate_question(
            "multi_select",
            "Select programming languages",
            2,
            ["Python", "Java"],
            correct_option_indices=[0, 5],
        )


def test_rejects_duplicate_multi_select_indexes():
    with pytest.raises(ValueError):
        validate_question(
            "multi_select",
            "Select programming languages",
            2,
            ["Python", "Java", "HTML"],
            correct_option_indices=[0, 0],
        )


def test_valid_short_answer():
    assert validate_question(
        "short_answer",
        "What is Python?",
        2,
    ) is True


def test_valid_long_answer():
    assert validate_question(
        "long_answer",
        "Explain object-oriented programming.",
        10,
    ) is True


def test_valid_image_upload():
    assert validate_question(
        "image_upload",
        "Upload a diagram of a computer network.",
        5,
    ) is True


def test_image_upload_requires_positive_marks():
    with pytest.raises(ValueError):
        validate_question(
            "image_upload",
            "Upload a diagram.",
            0,
        )


def test_rejects_negative_negative_marks():
    with pytest.raises(ValueError):
        validate_question(
            "short_answer",
            "Explain Python.",
            5,
            negative_marks=-1,
        )


def test_rejects_duplicate_option_text():
    with pytest.raises(ValueError):
        validate_question(
            "MCQ",
            "What is Python?",
            2,
            ["Python", "Python"],
            correct_option_index=0,
        )


def test_rejects_duplicate_options_with_different_case():
    with pytest.raises(ValueError):
        validate_question(
            "MCQ",
            "What is Python?",
            2,
            ["Python", "python"],
            correct_option_index=0,
        )


def test_rejects_empty_option_text():
    with pytest.raises(ValueError):
        validate_question(
            "MCQ",
            "What is Python?",
            2,
            ["Python", "  "],
            correct_option_index=0,
        )


def test_rejects_non_string_option():
    with pytest.raises(ValueError):
        validate_question(
            "MCQ",
            "What is Python?",
            2,
            ["Python", 123],
            correct_option_index=0,
        )


def test_rejects_non_integer_mcq_index():
    with pytest.raises(ValueError):
        validate_question(
            "MCQ",
            "What is Python?",
            2,
            ["Python", "Java"],
            correct_option_index=0.5,
        )


def test_rejects_multiple_correct_indexes_for_mcq():
    with pytest.raises(ValueError):
        validate_question(
            "MCQ",
            "What is Python?",
            2,
            ["Python", "Java"],
            correct_option_index=0,
            correct_option_indices=[0, 1],
        )


def test_rejects_correct_indexes_for_short_answer():
    with pytest.raises(ValueError):
        validate_question(
            "short_answer",
            "Explain Python.",
            5,
            correct_option_index=0,
        )


@pytest.mark.parametrize("marks", [-1, 0, math.inf, -math.inf, math.nan])
def test_rejects_invalid_mark_values(marks):
    with pytest.raises(ValueError):
        validate_question(
            "short_answer",
            "Explain Python.",
            marks,
        )


@pytest.mark.parametrize(
    "negative_marks",
    [-1, math.inf, -math.inf, math.nan],
)
def test_rejects_invalid_negative_mark_values(negative_marks):
    with pytest.raises(ValueError):
        validate_question(
            "short_answer",
            "Explain Python.",
            5,
            negative_marks=negative_marks,
)
            
