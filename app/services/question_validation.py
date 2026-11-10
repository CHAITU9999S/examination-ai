def validate_question(
    question_type,
    question_text,
    marks,
    options=None,
    negative_marks=0,
    correct_option_index=None
):
    if not question_text.strip():
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

        if correct_option_index >= len(options):
            raise ValueError("Correct option index is invalid")

    elif correct_option_index is not None:
        raise ValueError("Correct option index is only for MCQ")

    return True
