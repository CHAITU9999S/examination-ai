from datetime import datetime


def validate_exam_config(
    duration_minutes,
    start_time=None,
    end_time=None
):
    if duration_minutes <= 0:
        raise ValueError("Duration must be positive")

    if start_time and end_time:
        if end_time <= start_time:
            raise ValueError("End time must be after start time")

    if start_time and start_time < datetime.now(start_time.tzinfo):
        raise ValueError("Start time cannot be in the past")

    return True
