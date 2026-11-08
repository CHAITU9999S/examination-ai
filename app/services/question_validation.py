def validate_question(
    question_type,
    question_text,
    marks,
    options=None,
    negative_marks=0
):
    if not question_text.strip():
        raise ValueError("Question text cannot be empty")

    if marks <= 0:
        raise ValueError("Marks must be positive")

    if negative_marks < 0:
        raise ValueError("Negative marks cannot be below zero")

    allowed_types = [
        "MCQ", "MULTI_SELECT", "SHORT", "LONG", "IMAGE"
    ]

    if question_type not in allowed_types:
        raise ValueError("Invalid question type")

    if question_type in ["MCQ", "MULTI_SELECT"]:
        if not options or len(options) < 2:
            raise ValueError("At least two options are required")

    return True
