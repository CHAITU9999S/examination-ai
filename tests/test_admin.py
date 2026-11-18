
import pytest

from app.auth import hash_password
from app.models import User


@pytest.fixture
def admin(db_session):
    """Create an administrator account."""

    user = User(
        full_name="Test Administrator",
        email="admin@example.com",
        password_hash=hash_password("AdminPass123!"),
        role="admin",
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def examiner(db_session):
    """Create an examiner account."""

    user = User(
        full_name="Test Examiner",
        email="examiner@example.com",
        password_hash=hash_password("ExaminerPass123!"),
        role="examiner",
        is_active=True,
    )

    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    return user


@pytest.fixture
def student(db_session):
    """Create a student account."""

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


def get_auth_headers(client, email, password):
    """Log in and return authorization headers."""

    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": password,
        },
    )

    assert response.status_code == 200

    token = response.json()["access_token"]

    return {
        "Authorization": f"Bearer {token}",
    }


def test_admin_can_create_examiner(
    client,
    db_session,
    admin,
):
    """An administrator can create an examiner account."""

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.post(
        "/admin/users",
        headers=headers,
        json={
            "full_name": "New Examiner",
            "email": "newexaminer@example.com",
            "password": "ExaminerPass123!",
            "role": "examiner",
        },
    )

    assert response.status_code in (200, 201)

    created_user = db_session.query(User).filter(
        User.email == "newexaminer@example.com"
    ).first()

    assert created_user is not None
    assert created_user.role == "examiner"


def test_admin_can_create_another_admin(
    client,
    db_session,
    admin,
):
    """An administrator can create another administrator."""

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.post(
        "/admin/users",
        headers=headers,
        json={
            "full_name": "Second Administrator",
            "email": "admin2@example.com",
            "password": "SecondAdminPass123!",
            "role": "admin",
        },
    )

    assert response.status_code in (200, 201)

    created_user = db_session.query(User).filter(
        User.email == "admin2@example.com"
    ).first()

    assert created_user is not None
    assert created_user.role == "admin"


def test_admin_can_list_users(
    client,
    admin,
    student,
    examiner,
):
    """An administrator can view registered users."""

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.get(
        "/admin/users",
        headers=headers,
    )

    assert response.status_code == 200


def test_admin_can_deactivate_student(
    client,
    db_session,
    admin,
    student,
):
    """An administrator can deactivate a student."""

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.patch(
        f"/admin/users/{student.id}/status",
        headers=headers,
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 200

    db_session.refresh(student)

    assert student.is_active is False


def test_admin_can_reactivate_student(
    client,
    db_session,
    admin,
    student,
):
    """An administrator can reactivate a student."""

    student.is_active = False
    db_session.commit()

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.patch(
        f"/admin/users/{student.id}/status",
        headers=headers,
        json={
            "is_active": True,
        },
    )

    assert response.status_code == 200

    db_session.refresh(student)

    assert student.is_active is True


def test_admin_cannot_deactivate_self(
    client,
    admin,
):
    """An administrator cannot deactivate their own account."""

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.patch(
        f"/admin/users/{admin.id}/status",
        headers=headers,
        json={
            "is_active": False,
        },
    )

    assert response.status_code == 400


def test_admin_cannot_delete_self(
    client,
    admin,
):
    """An administrator cannot delete their own account."""

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.delete(
        f"/admin/users/{admin.id}",
        headers=headers,
    )

    assert response.status_code == 400


def test_admin_cannot_delete_last_active_admin(
    client,
    admin,
):
    """The last active administrator cannot be deleted."""

    headers = get_auth_headers(
        client,
        admin.email,
        "AdminPass123!",
    )

    response = client.delete(
        f"/admin/users/{admin.id}",
        headers=headers,
    )

    assert response.status_code == 400


def test_student_cannot_access_admin_users(
    client,
    student,
):
    """Students cannot access administrator endpoints."""

    headers = get_auth_headers(
        client,
        student.email,
        "StudentPass123!",
    )

    response = client.get(
        "/admin/users",
        headers=headers,
    )

    assert response.status_code == 403


def test_examiner_cannot_create_users(
    client,
    examiner,
):
    """Examiners cannot create administrator or examiner accounts."""

    headers = get_auth_headers(
        client,
        examiner.email,
        "ExaminerPass123!",
    )

    response = client.post(
        "/admin/users",
        headers=headers,
        json={
            "full_name": "Unauthorized User",
            "email": "unauthorized@example.com",
            "password": "UnauthorizedPass123!",
            "role": "examiner",
        },
    )

    assert response.status_code == 403
