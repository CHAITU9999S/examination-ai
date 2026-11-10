import pytest
from datetime import datetime, timedelta, timezone

from app.services.exam_config import validate_exam_config


def test_valid_exam_config():
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    assert validate_exam_config(60, start, end) is True


def test_rejects_zero_duration():
    with pytest.raises(ValueError):
        validate_exam_config(0)


def test_rejects_invalid_time_range():
    start = datetime.now(timezone.utc) + timedelta(hours=3)
    end = start - timedelta(hours=1)

    with pytest.raises(ValueError):
        validate_exam_config(60, start, end)


def test_rejects_past_start_time():
    start = datetime.now(timezone.utc) - timedelta(hours=1)

    with pytest.raises(ValueError):
        validate_exam_config(60, start)

def test_rejects_negative_duration():
    with pytest.raises(ValueError):
        validate_exam_config(-10)


def test_rejects_past_end_time():
    end = datetime.now(timezone.utc) - timedelta(hours=1)

    with pytest.raises(ValueError):
        validate_exam_config(60, end_time=end)


def test_rejects_mismatched_timezones():
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = datetime.now() + timedelta(hours=2)

    with pytest.raises(ValueError):
        validate_exam_config(60, start, end)
