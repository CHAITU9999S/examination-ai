
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


def test_login_accepts_email_with_different_letter_case(client, student):
    response = client.post(
        "/auth/login",
        json={
            "email": student.email.upper(),
            "password": "StudentPass123!",
        },
    )

    assert response.status_code == 200


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


def test_registration_rejects_email_with_different_letter_case(client, student):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Another Student",
            "email": student.email.upper(),
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
            "current_password": "StudentPass123!",
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
            "current_password": "WrongPassword123!",
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

def _login_token(client, email, password="StudentPass123!"):
    response = client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_profile_fields_have_independent_three_edit_limits(client, student):
    token = _login_token(client, student.email)
    headers = {"Authorization": f"Bearer {token}"}

    for name in ("First Updated Name", "Second Updated Name", "Third Updated Name"):
        response = client.patch(
            "/users/me/profile",
            headers=headers,
            json={"full_name": name},
        )
        assert response.status_code == 200

    fourth_name = client.patch(
        "/users/me/profile",
        headers=headers,
        json={"full_name": "Fourth Updated Name"},
    )
    assert fourth_name.status_code == 400
    assert "3 edit chances" in fourth_name.json()["detail"]

    # Exhausting the name allowance does not consume the email allowance.
    email_update = client.patch(
        "/users/me/profile",
        headers=headers,
        json={"email": "updated.student@example.com"},
    )
    assert email_update.status_code == 200
    assert email_update.json()["full_name_edit_count"] == 3
    assert email_update.json()["email_edit_count"] == 1


def test_profile_optional_fields_can_be_set_and_cleared(client, student):
    token = _login_token(client, student.email)
    headers = {"Authorization": f"Bearer {token}"}

    response = client.patch(
        "/users/me/profile",
        headers=headers,
        json={
            "department": "Computer Science",
            "date_of_birth": "2002-04-15",
        },
    )
    assert response.status_code == 200
    assert response.json()["department"] == "Computer Science"
    assert response.json()["date_of_birth"] == "2002-04-15"
    assert response.json()["department_edit_count"] == 1
    assert response.json()["date_of_birth_edit_count"] == 1

    clear_response = client.patch(
        "/users/me/profile",
        headers=headers,
        json={"department": None, "date_of_birth": None},
    )
    assert clear_response.status_code == 200
    assert clear_response.json()["department"] is None
    assert clear_response.json()["date_of_birth"] is None
    assert clear_response.json()["department_edit_count"] == 2
    assert clear_response.json()["date_of_birth_edit_count"] == 2


def test_profile_update_rejects_duplicate_email(client, student, db_session):
    other_user = User(
        full_name="Other Student",
        email="other.student@example.com",
        password_hash=hash_password("OtherPass123!"),
        role="student",
        is_active=True,
    )
    db_session.add(other_user)
    db_session.commit()

    token = _login_token(client, student.email)
    response = client.patch(
        "/users/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"email": other_user.email},
    )
    assert response.status_code == 409


def test_login_history_returns_only_latest_ten_successful_logins(client, student):
    token = None
    for index in range(12):
        response = client.post(
            "/auth/login",
            json={"email": student.email, "password": "StudentPass123!"},
            headers={"User-Agent": f"ExamGuard Test Browser {index}"},
        )
        assert response.status_code == 200
        token = response.json()["access_token"]

    history_response = client.get(
        "/users/me/login-history",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert history_response.status_code == 200
    history = history_response.json()
    assert len(history) == 10
    assert history[0]["user_agent"] == "ExamGuard Test Browser 11"
    assert history[-1]["user_agent"] == "ExamGuard Test Browser 2"
    assert all(item["logged_in_at"] for item in history)
    assert all(item["ip_address"] for item in history)


def test_login_history_requires_authentication(client):
    response = client.get("/users/me/login-history")
    assert response.status_code in (401, 403)

@pytest.mark.parametrize(
    ("field", "values"),
    [
        ("email", ["first.email@example.com", "second.email@example.com", "third.email@example.com", "fourth.email@example.com"]),
        ("department", ["Department One", "Department Two", "Department Three", "Department Four"]),
        ("date_of_birth", ["2001-01-01", "2001-02-01", "2001-03-01", "2001-04-01"]),
    ],
)
def test_each_profile_field_stops_after_its_own_third_edit(client, student, field, values):
    token = _login_token(client, student.email)
    headers = {"Authorization": f"Bearer {token}"}

    for value in values[:3]:
        response = client.patch(
            "/users/me/profile",
            headers=headers,
            json={field: value},
        )
        assert response.status_code == 200

    rejected = client.patch(
        "/users/me/profile",
        headers=headers,
        json={field: values[3]},
    )
    assert rejected.status_code == 400
    assert "3 edit chances" in rejected.json()["detail"]

def test_login_history_is_private_to_each_account(client, student, db_session):
    another_user = User(
        full_name="Second Student",
        email="second.student@example.com",
        password_hash=hash_password("SecondPass123!"),
        role="student",
        is_active=True,
    )
    db_session.add(another_user)
    db_session.commit()

    first_token = _login_token(client, student.email)
    second_token = _login_token(client, another_user.email, "SecondPass123!")

    first_history = client.get(
        "/users/me/login-history",
        headers={"Authorization": f"Bearer {first_token}"},
    )
    second_history = client.get(
        "/users/me/login-history",
        headers={"Authorization": f"Bearer {second_token}"},
    )

    assert first_history.status_code == 200
    assert second_history.status_code == 200
    assert len(first_history.json()) == 1
    assert len(second_history.json()) == 1
    assert first_history.json()[0]["id"] != second_history.json()[0]["id"]

