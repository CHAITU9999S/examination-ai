
from datetime import datetime, timedelta, timezone
from typing import Optional


# ==========================================
# CURRENT UTC TIME
# ==========================================

def get_current_utc_time() -> datetime:
    """
    Return the current UTC time without timezone information.

    This matches the existing database DateTime convention.
    """

    return datetime.now(timezone.utc).replace(tzinfo=None)


# ==========================================
# DATETIME NORMALIZATION
# ==========================================

def normalize_to_utc(
    value: Optional[datetime],
) -> Optional[datetime]:
    """
    Convert a datetime to timezone-aware UTC.

    Naive datetimes are interpreted as UTC.
    """

    if value is None:
        return None

    if not isinstance(value, datetime):
        raise TypeError("Value must be a datetime object.")

    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)

    return value.astimezone(timezone.utc)


def normalize_to_naive_utc(
    value: Optional[datetime],
) -> Optional[datetime]:
    """
    Convert a datetime to UTC without timezone information.

    Use this for the project's existing naive database columns.
    """

    normalized = normalize_to_utc(value)

    if normalized is None:
        return None

    return normalized.replace(tzinfo=None)


# ==========================================
# EXAM SCHEDULE VALIDATION
# ==========================================

def is_exam_available(
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    current_time: Optional[datetime] = None,
) -> bool:
    """
    Check whether the current time is inside the exam schedule.

    Both start_time and end_time are required.
    """

    if start_time is None or end_time is None:
        return False

    start = normalize_to_utc(start_time)
    end = normalize_to_utc(end_time)

    current = normalize_to_utc(
        current_time or get_current_utc_time()
    )

    if start is None or end is None or current is None:
        return False

    if end <= start:
        return False

    return start <= current <= end


# ==========================================
# REMAINING TIME
# ==========================================

def get_remaining_seconds(
    expires_at: datetime,
    current_time: Optional[datetime] = None,
) -> int:
    """
    Calculate remaining examination time in seconds.

    Returns zero when the examination has expired.
    """

    expiry = normalize_to_utc(expires_at)

    current = normalize_to_utc(
        current_time or get_current_utc_time()
    )

    if expiry is None or current is None:
        return 0

    remaining = (expiry - current).total_seconds()

    return max(0, int(remaining))


# ==========================================
# EXAM EXPIRY CALCULATION
# ==========================================

def calculate_exam_expiry(
    started_at: datetime,
    duration_minutes: int,
    exam_end_time: Optional[datetime] = None,
) -> datetime:
    """
    Calculate the exam session expiry time.

    The expiry cannot exceed the examination's scheduled end time.
    """

    if (
        isinstance(duration_minutes, bool)
        or not isinstance(duration_minutes, int)
        or duration_minutes <= 0
    ):
        raise ValueError(
            "Exam duration must be a positive integer."
        )

    start = normalize_to_utc(started_at)

    if start is None:
        raise ValueError("Exam start time is required.")

    expiry = start + timedelta(
        minutes=duration_minutes
    )

    if exam_end_time is not None:
        scheduled_end = normalize_to_utc(exam_end_time)

        if scheduled_end is None or scheduled_end <= start:
            raise ValueError(
                "Exam scheduled end time must be after its start time."
            )

        expiry = min(expiry, scheduled_end)

    return expiry.replace(tzinfo=None)
