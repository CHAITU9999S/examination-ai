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
    start = datetime.now(timezone.utc) + timedelta(hours=2)
    end = start + timedelta(hours=1)

    with pytest.raises(ValueError):
        validate_exam_config(60, start, end)


def test_rejects_past_start_time():
    start = datetime.now(timezone.utc) - timedelta(hours=1)

    with pytest.raises(ValueError):
        validate_exam_config(60, start)
