
from datetime import datetime, timedelta, timezone

from jose import jwt

from app.auth import (
    JWT_SECRET_KEY,
    JWT_ALGORITHM,
    hash_password,
    verify_password,
    create_access_token,
    create_exam_access_token,
    verify_token
)


def test_password_hashing():
    password = "TestPassword123"
    hashed = hash_password(password)

    assert hashed != password
    assert verify_password(password, hashed)


def test_wrong_password_rejected():
    hashed = hash_password("TestPassword123")

    assert not verify_password("WrongPassword", hashed)


def test_access_token_creation():
    token = create_access_token({"sub": "101"})
    payload = verify_token(token)

    assert payload is not None
    assert payload["sub"] == "101"
    assert payload["token_type"] == "access"


def test_exam_token_creation():
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

    token = create_exam_access_token(
        exam_id=10,
        student_id=101,
        session_id=501,
        expires_at=expires_at
    )

    payload = verify_token(token)

    assert payload is not None
    assert payload["token_type"] == "exam"
    assert payload["exam_id"] == 10
    assert payload["student_id"] == 101
    assert payload["session_id"] == 501
    assert payload["sub"] == "101"
    assert payload["exp"] > datetime.now(timezone.utc).timestamp()


def test_expired_token_rejected():
    now = datetime.now(timezone.utc)

    token = jwt.encode(
        {
            "sub": "101",
            "iat": now - timedelta(minutes=2),
            "exp": now - timedelta(minutes=1),
            "token_type": "access",
        },
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM,
    )

    assert verify_token(token) is None


def test_invalid_token_rejected():
    assert verify_token("invalid.token.value") is None
    
