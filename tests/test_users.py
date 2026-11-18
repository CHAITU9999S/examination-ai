
import pytest

from app.auth import hash_password
from app.models import User


@pytest.fixture
def student(db_session):
    """Create a student account for testing."""

    user = User(
        full_name="Test Student",
        email="student@example.com",
        password_hash=hash_password("StudentPass123!"),
        role="student",
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


def test_get_current_user(client, student):
    """An authenticated student can retrieve their profile."""

    # Log in to obtain an access token.
    login_response = client.post(
        "/auth/login",
        json={
            "email": student.email,
            "password": "StudentPass123!",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/users/me",
        headers={
            "Authorization": f"Bearer {token}",
        },
    )

    assert response.status_code == 200
    assert response.json()["email"] == student.email
    assert response.json()["role"] == "student"


def test_get_current_user_without_token(client):
    """Unauthenticated users cannot access their profile."""

    response = client.get("/users/me")

    assert response.status_code in (401, 403)


def test_student_registration(client, db_session):
    """A student can register through the public registration endpoint."""

    response = client.post(
        "/auth/register",
        json={
            "full_name": "New Student",
            "email": "newstudent@example.com",
            "password": "StudentPass123!",
        },
    )

    assert response.status_code in (200, 201)

    created_user = db_session.query(User).filter(
        User.email == "newstudent@example.com"
    ).first()

    assert created_user is not None
    assert created_user.role == "student"
    assert created_user.is_active is True


def test_duplicate_email_registration(client, student):
    """Registration rejects an email that already exists."""

    response = client.post(
        "/auth/register",
        json={
            "full_name": "Duplicate Student",
            "email": student.email,
            "password": "AnotherPass123!",
        },
    )

    assert response.status_code == 409


def test_password_change(client, student):
    """A student can change their password using the current password."""

    login_response = client.post(
        "/auth/login",
        json={
            "email": student.email,
            "password": "StudentPass123!",
        },
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.patch(
        "/users/me/password",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "old_password": "StudentPass123!",
            "new_password": "NewStudentPass456!",
        },
    )

    assert response.status_code == 200

    # Verify the new password works.
    new_login_response = client.post(
        "/auth/login",
        json={
            "email": student.email,
            "password": "NewStudentPass456!",
        },
    )

    assert new_login_response.status_code == 200


def test_password_change_rejects_wrong_old_password(
    client,
    student,
):
    """A wrong current password cannot be used to change a password."""

    login_response = client.post(
        "/auth/login",
        json={
            "email": student.email,
            "password": "StudentPass123!",
        },
    )

    token = login_response.json()["access_token"]

    response = client.patch(
        "/users/me/password",
        headers={
            "Authorization": f"Bearer {token}",
        },
        json={
            "old_password": "WrongPassword123!",
            "new_password": "NewStudentPass456!",
        },
    )

    assert response.status_code == 400


def test_inactive_student_cannot_login(
    client,
    db_session,
):
    """An inactive student account cannot log in."""

    user = User(
        full_name="Inactive Student",
        email="inactive@example.com",
        password_hash=hash_password("StudentPass123!"),
        role="student",
        is_active=False,
    )

    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={
            "email": "inactive@example.com",
            "password": "StudentPass123!",
        },
    )

    assert response.status_code == 403
