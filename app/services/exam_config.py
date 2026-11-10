
from datetime import datetime, timezone


def validate_exam_config(
    duration_minutes,
    start_time=None,
    end_time=None
):
    if duration_minutes <= 0:
        raise ValueError("Duration must be positive")

    if start_time and end_time:
        if start_time.tzinfo != end_time.tzinfo:
            raise ValueError("Start and end times must use compatible timezones")

        if end_time <= start_time:
            raise ValueError("End time must be after start time")

    now = datetime.now(timezone.utc)

    if start_time:
        normalized_start = (
            start_time.replace(tzinfo=timezone.utc)
            if start_time.tzinfo is None
            else start_time.astimezone(timezone.utc)
        )

        if normalized_start < now:
            raise ValueError("Start time cannot be in the past")

    if end_time:
        normalized_end = (
            end_time.replace(tzinfo=timezone.utc)
            if end_time.tzinfo is None
            else end_time.astimezone(timezone.utc)
        )

        if normalized_end < now:
            raise ValueError("End time cannot be in the past")

    return True
            
