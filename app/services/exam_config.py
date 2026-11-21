
import math
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

INDIA_TIME_ZONE = ZoneInfo("Asia/Kolkata")


# -----------------------------------------
# VALID CONFIGURATION VALUES
# -----------------------------------------

VALID_DIFFICULTIES = {
    "easy",
    "medium",
    "hard"
}

VALID_QUESTION_TYPES = {
    "MCQ",
    "multi_select",
    "short_answer",
    "long_answer",
    "image_upload"
}


# -----------------------------------------
# DATETIME NORMALIZATION
# -----------------------------------------

def normalize_to_naive_utc(value):
    """
    Normalize a datetime already stored or represented as UTC.

    Database DateTime columns use naive UTC values. Treating those values as
    IST would shift deadlines by 5 hours 30 minutes and expire active sessions.
    """

    if value is None:
        return None

    if not isinstance(value, datetime):
        raise ValueError("Schedule values must be valid datetimes")

    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc).replace(tzinfo=None)


def normalize_schedule_input_to_naive_utc(value):
    """
    Convert an API schedule input to naive UTC for database storage.

    Explicit offsets are preserved. Timezone-naive schedule inputs are
    interpreted as India Standard Time (Asia/Kolkata).
    """

    if value is None:
        return None

    if not isinstance(value, datetime):
        raise ValueError("Schedule values must be valid datetimes")

    if value.tzinfo is None:
        value = value.replace(tzinfo=INDIA_TIME_ZONE)

    return value.astimezone(timezone.utc).replace(tzinfo=None)


# -----------------------------------------
# DISTRIBUTION VALIDATION
# -----------------------------------------

def validate_distribution(
    distribution,
    allowed_values,
    total_questions,
    field_name
):
    """Validate question difficulty or type distributions."""

    if not isinstance(distribution, dict) or not distribution:
        raise ValueError(
            f"{field_name} must be a non-empty dictionary"
        )

    if (
        isinstance(total_questions, bool)
        or not isinstance(total_questions, int)
        or total_questions <= 0
    ):
        raise ValueError(
            "Total questions must be a positive integer "
            "when using distributions"
        )

    for key, count in distribution.items():

        if key not in allowed_values:
            raise ValueError(
                f"Invalid {field_name} value: {key}"
            )

        if (
            isinstance(count, bool)
            or not isinstance(count, int)
        ):
            raise ValueError(
                f"Counts in {field_name} must be integers"
            )

        if count < 0:
            raise ValueError(
                f"Counts in {field_name} cannot be negative"
            )

    if sum(distribution.values()) != total_questions:
        raise ValueError(
            f"{field_name} counts must equal total_questions"
        )


# -----------------------------------------
# EXAM CONFIGURATION VALIDATION
# -----------------------------------------

def validate_exam_config(
    duration_minutes,
    start_time=None,
    end_time=None,
    selection_rules=None,
    total_questions=0,
    gaze_tracking_sensitivity=None,
    max_tab_switch_warnings=None
):
    """
    Validate exam duration, schedule, question selection
    rules and proctoring configuration.
    """

    # -------------------------------------
    # EXAM DURATION
    # -------------------------------------

    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes <= 0
    ):
        raise ValueError(
            "Duration must be a positive integer"
        )

    # -------------------------------------
    # EXAM SCHEDULE
    # -------------------------------------

    normalized_start = normalize_schedule_input_to_naive_utc(start_time)
    normalized_end = normalize_schedule_input_to_naive_utc(end_time)

    if (normalized_start is None) != (normalized_end is None):
        raise ValueError("Set both examination start and end times, or leave both empty.")

    if normalized_start and normalized_end:
        if normalized_end <= normalized_start:
            raise ValueError(
                "End time must be after start time"
            )

    now = datetime.now(timezone.utc).replace(
        tzinfo=None
    )

    if normalized_start and normalized_start < now:
        raise ValueError(
            "Start time cannot be in the past"
        )

    if normalized_end and normalized_end <= now:
        raise ValueError(
            "End time must be in the future"
        )

    # -------------------------------------
    # TOTAL QUESTION COUNT
    # -------------------------------------

    if (
        isinstance(total_questions, bool)
        or not isinstance(total_questions, int)
        or total_questions < 0
    ):
        raise ValueError(
            "Total questions must be a non-negative integer"
        )

    # -------------------------------------
    # QUESTION SELECTION RULES
    # -------------------------------------

    if selection_rules is not None:

        if not isinstance(selection_rules, dict):
            raise ValueError(
                "Selection rules must be a dictionary"
            )

        allowed_keys = {
            "difficulty",
            "difficulty_counts",
            "question_type_counts",
            "group_counts",
        }

        if not set(selection_rules).issubset(allowed_keys):
            raise ValueError(
                "Unknown selection rule"
            )

        has_difficulty_counts = (
            "difficulty_counts" in selection_rules
        )

        has_type_counts = (
            "question_type_counts" in selection_rules
        )
        has_group_counts = "group_counts" in selection_rules

        if has_group_counts:
            if has_difficulty_counts or has_type_counts or "difficulty" in selection_rules:
                raise ValueError(
                    "Use group_counts alone for exact type-by-difficulty selection."
                )
            group_counts = selection_rules["group_counts"]
            if not isinstance(group_counts, dict) or not group_counts:
                raise ValueError("group_counts must be a non-empty dictionary.")
            allowed_groups = {
                f"{difficulty}|{question_type}"
                for difficulty in VALID_DIFFICULTIES
                for question_type in VALID_QUESTION_TYPES
            }
            for group, count in group_counts.items():
                if group not in allowed_groups:
                    raise ValueError(f"Invalid question type/difficulty group: {group}")
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise ValueError("group_counts values must be non-negative integers.")
            if sum(group_counts.values()) != total_questions:
                raise ValueError("group_counts must add up to total_questions.")

        # Both distributions must be configured together.
        if has_difficulty_counts != has_type_counts:
            raise ValueError(
                "Both difficulty_counts and "
                "question_type_counts are required"
            )

        # Single difficulty selection.
        if "difficulty" in selection_rules:

            difficulty = selection_rules["difficulty"]

            if difficulty not in VALID_DIFFICULTIES:
                raise ValueError(
                    "Invalid difficulty. Use easy, medium or hard."
                )

            if has_difficulty_counts:
                raise ValueError(
                    "Use either difficulty or distribution rules, "
                    "not both"
                )

        # Distribution-based selection.
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

    # -------------------------------------
    # PROCTORING SENSITIVITY
    # -------------------------------------

    if gaze_tracking_sensitivity is not None:

        if (
            isinstance(gaze_tracking_sensitivity, bool)
            or not isinstance(
                gaze_tracking_sensitivity,
                (int, float)
            )
            or not math.isfinite(gaze_tracking_sensitivity)
            or not 0 <= gaze_tracking_sensitivity <= 1
        ):
            raise ValueError(
                "Gaze tracking sensitivity must be between 0 and 1"
            )

    # -------------------------------------
    # MAXIMUM TAB-SWITCH WARNINGS
    # -------------------------------------

    if max_tab_switch_warnings is not None:

        if (
            isinstance(max_tab_switch_warnings, bool)
            or not isinstance(max_tab_switch_warnings, int)
            or max_tab_switch_warnings < 0
        ):
            raise ValueError(
                "Maximum tab-switch warnings must be "
                "a non-negative integer"
            )

    return True
    
