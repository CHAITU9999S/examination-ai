from datetime import datetime
from pydantic import ValidationError
import pytest

from app.schemas import ExamCreate


def test_exam_requires_positive_duration():
    with pytest.raises(ValidationError):
        ExamCreate(
            title="Test Exam",
            subject="Python",
            duration_minutes=0
        )


def test_exam_accepts_valid_configuration():
    exam = ExamCreate(
        title="Python Test",
        subject="Programming",
        duration_minutes=60,
        negative_marking=True,
        proctoring_enabled=True
    )

    assert exam.duration_minutes == 60
    assert exam.negative_marking is True


def test_exam_rejects_invalid_datetime_format():
    with pytest.raises(ValidationError):
        ExamCreate(
            title="Test Exam",
            subject="Python",
            duration_minutes=60,
            start_time="not-a-date"
        )
