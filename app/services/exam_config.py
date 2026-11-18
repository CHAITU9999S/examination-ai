from datetime import datetime, timezone


VALID_DIFFICULTIES = {"Easy", "Medium", "Hard"}

VALID_QUESTION_TYPES = {
    "MCQ",
    "multi_select",
    "short_answer",
    "long_answer",
    "image_upload"
}


def normalize_to_naive_utc(value):
    """
    Convert a datetime to naive UTC.

    Naive datetime values are interpreted as UTC.
    Timezone-aware values are converted to UTC first.
    """

    if value is None:
        return None

    if value.tzinfo is None:
        return value

    return value.astimezone(
        timezone.utc
    ).replace(tzinfo=None)


def validate_distribution(
    distribution,
    allowed_values,
    total_questions,
    field_name
):
    if not isinstance(distribution, dict) or not distribution:
        raise ValueError(
            f"{field_name} must be a non-empty dictionary"
        )

    for key, count in distribution.items():
        if key not in allowed_values:
            raise ValueError(
                f"Invalid {field_name} value: {key}"
            )

        if isinstance(count, bool) or not isinstance(count, int):
            raise ValueError(
                f"Counts in {field_name} must be integers"
            )

        if count < 0:
            raise ValueError(
                f"Counts in {field_name} cannot be negative"
            )

    if total_questions <= 0:
        raise ValueError(
            "Total questions must be positive when using distributions"
        )

    if sum(distribution.values()) != total_questions:
        raise ValueError(
            f"{field_name} counts must equal total_questions"
        )


def validate_exam_config(
    duration_minutes,
    start_time=None,
    end_time=None,
    selection_rules=None,
    total_questions=0,
    gaze_tracking_sensitivity=None,
    max_tab_switch_warnings=None
):
    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes <= 0
    ):
        raise ValueError("Duration must be a positive integer")

    normalized_start = normalize_to_naive_utc(start_time)
    normalized_end = normalize_to_naive_utc(end_time)

    if normalized_start and normalized_end:
        if normalized_end <= normalized_start:
            raise ValueError("End time must be after start time")

    now = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    if normalized_start and normalized_start < now:
        raise ValueError("Start time cannot be in the past")

    if normalized_end and normalized_end <= now:
        raise ValueError("End time must be in the future")

    if selection_rules is not None:
        if not isinstance(selection_rules, dict):
            raise ValueError("Selection rules must be a dictionary")

        allowed_keys = {
            "difficulty",
            "difficulty_counts",
            "question_type_counts"
        }

        if not set(selection_rules).issubset(allowed_keys):
            raise ValueError("Unknown selection rule")

        has_difficulty_counts = (
            "difficulty_counts" in selection_rules
        )

        has_type_counts = (
            "question_type_counts" in selection_rules
        )

        if has_difficulty_counts != has_type_counts:
            raise ValueError(
                "Both difficulty_counts and question_type_counts are required"
            )

        if "difficulty" in selection_rules:
            if selection_rules["difficulty"] not in VALID_DIFFICULTIES:
                raise ValueError("Invalid difficulty")

            if has_difficulty_counts:
                raise ValueError(
                    "Use either difficulty or distribution rules, not both"
                )

        if has_difficulty_counts:
            validate_distribution(
                selection_rules["difficulty_counts"],
                VALID_DIFFICULTIES,
                total_questions,
                "difficulty_counts"
            )

            validate_distribution(
                selection_rules["question_type_counts"],
                VALID_QUESTION_TYPES,
                total_questions,
                "question_type_counts"
            )

    if gaze_tracking_sensitivity is not None:
        if (
            isinstance(gaze_tracking_sensitivity, bool)
            or not isinstance(gaze_tracking_sensitivity, (int, float))
            or not 0 <= gaze_tracking_sensitivity <= 1
        ):
            raise ValueError(
                "Gaze tracking sensitivity must be between 0 and 1"
            )

    if max_tab_switch_warnings is not None:
        if (
            isinstance(max_tab_switch_warnings, bool)
            or not isinstance(max_tab_switch_warnings, int)
            or max_tab_switch_warnings < 0
        ):
            raise ValueError(
                "Maximum tab-switch warnings cannot be negative"
            )

    return True
        
