
def validate_question(
    question_type,
    question_text,
    marks,
    options=None,
    negative_marks=0,
    correct_option_index=None,
    correct_option_indices=None
):
    if not question_text or not question_text.strip():
        raise ValueError("Question text cannot be empty")

    if marks <= 0:
        raise ValueError("Marks must be positive")

    if negative_marks < 0:
        raise ValueError("Negative marks cannot be below zero")

    allowed_types = [
        "MCQ",
        "multi_select",
        "short_answer",
        "long_answer",
        "image_upload"
    ]

    if question_type not in allowed_types:
        raise ValueError("Invalid question type")

    if question_type in ["MCQ", "multi_select"]:
        if not options or len(options) < 2:
            raise ValueError("At least two options are required")

    if question_type == "MCQ":
        if correct_option_index is None:
            raise ValueError("MCQ must have exactly one correct option")

        if correct_option_index < 0 or correct_option_index >= len(options):
            raise ValueError("Correct option index is invalid")

        if correct_option_indices is not None:
            raise ValueError("Use correct_option_index for MCQ")

    elif question_type == "multi_select":
        if not correct_option_indices:
            raise ValueError("Multi-select must have correct options")

        if correct_option_index is not None:
            raise ValueError("Use correct_option_indices for multi-select")

        if len(set(correct_option_indices)) != len(correct_option_indices):
            raise ValueError("Duplicate correct option indexes are not allowed")

        for index in correct_option_indices:
            if index < 0 or index >= len(options):
                raise ValueError("Correct option index is invalid")

    elif correct_option_index is not None or correct_option_indices is not None:
        raise ValueError("Correct option indexes are only for MCQ and multi-select")

    return True
            
