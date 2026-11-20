
import pytest
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

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


def test_accepts_mixed_timezone_representations():
    start = datetime.now(timezone.utc) + timedelta(hours=1)

    # Naive schedule values are interpreted as India Standard Time.
    end = (
        datetime.now(timezone.utc) + timedelta(hours=2)
    ).astimezone(ZoneInfo("Asia/Kolkata")).replace(tzinfo=None)

    assert validate_exam_config(60, start, end) is True


def test_valid_distribution_rules():
    rules = {
        "difficulty_counts": {
            "easy": 2,
            "medium": 1,
            "hard": 1
        },
        "question_type_counts": {
            "MCQ": 2,
            "short_answer": 1,
            "long_answer": 1
        }
    }

    assert validate_exam_config(
        60,
        selection_rules=rules,
        total_questions=4
    ) is True


def test_rejects_missing_question_type_distribution():
    rules = {
        "difficulty_counts": {
            "Easy": 2,
            "Medium": 2
        }
    }

    with pytest.raises(ValueError):
        validate_exam_config(
            60,
            selection_rules=rules,
            total_questions=4
        )


def test_rejects_missing_difficulty_distribution():
    rules = {
        "question_type_counts": {
            "MCQ": 4
        }
    }

    with pytest.raises(ValueError):
        validate_exam_config(
            60,
            selection_rules=rules,
            total_questions=4
        )


def test_rejects_unknown_selection_rule():
    rules = {
        "difficulty": "Easy",
        "random_selection": True
    }

    with pytest.raises(ValueError):
        validate_exam_config(
            60,
            selection_rules=rules
        )


def test_rejects_conflicting_difficulty_rules():
    rules = {
        "difficulty": "Easy",
        "difficulty_counts": {
            "Easy": 4
        },
        "question_type_counts": {
            "MCQ": 4
        }
    }

    with pytest.raises(ValueError):
        validate_exam_config(
            60,
            selection_rules=rules,
            total_questions=4
        )


def test_rejects_distribution_with_wrong_total():
    rules = {
        "difficulty_counts": {
            "Easy": 2,
            "Medium": 1
        },
        "question_type_counts": {
            "MCQ": 3
        }
    }

    with pytest.raises(ValueError):
        validate_exam_config(
            60,
            selection_rules=rules,
            total_questions=4
)
        
