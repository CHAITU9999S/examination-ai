
import math


VALID_QUESTION_TYPES = {
    "mcq",
    "multi_select",
    "short_answer",
    "long_answer",
    "image_upload",
}


def validate_question(
    question_type,
    question_text,
    marks,
    options=None,
    negative_marks=0,
    correct_option_index=None,
    correct_option_indices=None
):
    """Validate question content, marks and correct options."""

    # Question type
    if question_type not in VALID_QUESTION_TYPES:
        raise ValueError("Invalid question type")

    # Question text
    if not isinstance(question_text, str) or not question_text.strip():
        raise ValueError("Question text cannot be empty")

    # Marks
    if (
        isinstance(marks, bool)
        or not isinstance(marks, (int, float))
        or not math.isfinite(marks)
        or marks <= 0
    ):
        raise ValueError("Marks must be a positive finite number")

    # Negative marks
    if (
        isinstance(negative_marks, bool)
        or not isinstance(negative_marks, (int, float))
        or not math.isfinite(negative_marks)
        or negative_marks < 0
    ):
        raise ValueError(
            "Negative marks must be a non-negative finite number"
        )

    # Options and correct answers
    if question_type in {"mcq", "multi_select"}:

        if not isinstance(options, list) or len(options) < 2:
            raise ValueError("At least two options are required")

        for option in options:
            if isinstance(option, str):
                if not option.strip():
                    raise ValueError("Option text cannot be empty")

            elif isinstance(option, dict):
                if (
                    not isinstance(option.get("text"), str)
                    or not option["text"].strip()
                ):
                    raise ValueError("Every option must have valid text")

            else:
                raise ValueError(
                    "Each option must be a string or an option dictionary"
                )

    if question_type == "mcq":

        if correct_option_index is None:
            raise ValueError(
                "MCQ must have exactly one correct option"
            )

        if (
            isinstance(correct_option_index, bool)
            or not isinstance(correct_option_index, int)
        ):
            raise ValueError("Correct option index must be an integer")

        if not 0 <= correct_option_index < len(options):
            raise ValueError("Correct option index is invalid")

        if correct_option_indices is not None:
            raise ValueError(
                "Use correct_option_index for MCQ"
            )

    elif question_type == "multi_select":

        if not isinstance(correct_option_indices, list) or not correct_option_indices:
            raise ValueError(
                "Multi-select must have at least one correct option"
            )

        if correct_option_index is not None:
            raise ValueError(
                "Use correct_option_indices for multi-select"
            )

        if any(
            isinstance(index, bool) or not isinstance(index, int)
            for index in correct_option_indices
        ):
            raise ValueError(
                "Correct option indexes must be integers"
            )

        if len(set(correct_option_indices)) != len(correct_option_indices):
            raise ValueError(
                "Duplicate correct option indexes are not allowed"
            )

        for index in correct_option_indices:
            if not 0 <= index < len(options):
                raise ValueError("Correct option index is invalid")

    elif (
        correct_option_index is not None
        or correct_option_indices is not None
    ):
        raise ValueError(
            "Correct option indexes are only for MCQ and multi-select"
        )

    return True
        
