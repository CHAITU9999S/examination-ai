from app.auth import (
    hash_password,
    verify_password,
    create_access_token,
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
