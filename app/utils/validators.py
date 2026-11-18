
import math
import re
from pathlib import Path
from typing import Optional


# ==========================================
# EMAIL VALIDATION
# ==========================================

EMAIL_PATTERN = re.compile(
    r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@"
    r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?"
    r"(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$"
)


def validate_email(email: str) -> bool:
    """Validate basic email address syntax."""

    if not isinstance(email, str):
        return False

    email = email.strip()

    if len(email) > 254 or not email:
        return False

    if not EMAIL_PATTERN.fullmatch(email):
        return False

    return True


# ==========================================
# PASSWORD VALIDATION
# ==========================================

def validate_password(
    password: str,
    minimum_length: int = 8,
) -> bool:
    """
    Validate password strength.

    Requires:
    - Minimum length
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    """

    if not isinstance(password, str):
        return False

    if (
        isinstance(minimum_length, bool)
        or not isinstance(minimum_length, int)
        or minimum_length < 1
    ):
        raise ValueError("Minimum password length must be positive.")

    if len(password) < minimum_length:
        return False

    if len(password) > 128:
        return False

    return all(
        (
            re.search(r"[A-Z]", password),
            re.search(r"[a-z]", password),
            re.search(r"\d", password),
            re.search(r"[^A-Za-z0-9]", password),
        )
    )


# ==========================================
# NUMERIC VALIDATION
# ==========================================

def validate_positive_number(
    value,
) -> bool:
    """Check whether a value is a positive finite number."""

    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    return math.isfinite(value) and value > 0


def validate_non_negative_number(
    value,
) -> bool:
    """Check whether a value is a non-negative finite number."""

    if isinstance(value, bool):
        return False

    if not isinstance(value, (int, float)):
        return False

    return math.isfinite(value) and value >= 0


# ==========================================
# INTEGER VALIDATION
# ==========================================

def validate_positive_integer(
    value,
) -> bool:
    """Check whether a value is a positive integer."""

    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value > 0
    )


def validate_non_negative_integer(
    value,
) -> bool:
    """Check whether a value is a non-negative integer."""

    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and value >= 0
    )


# ==========================================
# TEXT VALIDATION
# ==========================================

def validate_text(
    value: str,
    minimum_length: int = 1,
    maximum_length: Optional[int] = None,
) -> bool:
    """Validate non-empty text and optional length limits."""

    if not isinstance(value, str):
        return False

    if (
        isinstance(minimum_length, bool)
        or not isinstance(minimum_length, int)
        or minimum_length < 0
    ):
        raise ValueError("Minimum length must be a non-negative integer.")

    if maximum_length is not None:
        if (
            isinstance(maximum_length, bool)
            or not isinstance(maximum_length, int)
            or maximum_length < minimum_length
        ):
            raise ValueError("Maximum length is invalid.")

    cleaned = value.strip()

    if len(cleaned) < minimum_length:
        return False

    if maximum_length is not None and len(cleaned) > maximum_length:
        return False

    return True


# ==========================================
# WORD COUNT VALIDATION
# ==========================================

def validate_word_count(
    text: str,
    maximum_words: int,
    minimum_words: int = 0,
) -> bool:
    """Check whether text contains an allowed number of words."""

    if not isinstance(text, str):
        return False

    if (
        not validate_non_negative_integer(maximum_words)
        and maximum_words != 0
    ):
        return False

    if not validate_non_negative_integer(minimum_words):
        return False

    if minimum_words > maximum_words:
        return False

    word_count = len(text.split())

    return minimum_words <= word_count <= maximum_words


# ==========================================
# FILENAME VALIDATION
# ==========================================

def validate_filename(
    filename: str,
) -> bool:
    """
    Validate a filename without accepting directory paths.

    This does not replace file-content validation.
    """

    if not isinstance(filename, str) or not filename:
        return False

    if filename in {".", ".."}:
        return False

    if Path(filename).name != filename:
        return False

    if "/" in filename or "\\" in filename:
        return False

    if any(ord(character) < 32 for character in filename):
        return False

    return len(filename) <= 255
