import pytest

from app.auth import hash_password, verify_password
from app.models import AdminActivityLog, User


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
        json={"email": email, "password": password},
    )
    assert response.status_code == 200
    return {
        "Authorization": f"Bearer {response.json()['access_token']}",
    }


def test_admin_can_create_examiner_and_department_is_saved(
    client, db_session, admin
):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.post(
        "/admin/users",
        headers=headers,
        json={
            "full_name": "New Examiner",
            "email": "NewExaminer@example.com",
            "department": "Computer Science",
            "password": "ExaminerPass123!",
            "role": "examiner",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "examiner"
    assert response.json()["department"] == "Computer Science"

    created_user = db_session.query(User).filter(
        User.email == "newexaminer@example.com"
    ).first()
    assert created_user is not None
    assert created_user.role == "examiner"
    assert created_user.department == "Computer Science"
    assert created_user.password_hash != "ExaminerPass123!"
    assert verify_password("ExaminerPass123!", created_user.password_hash)

    log = db_session.query(AdminActivityLog).filter(
        AdminActivityLog.action == "examiner_created"
    ).one()
    assert log.actor_user_id == admin.id
    assert log.target_user_id == created_user.id


def test_admin_can_create_another_admin(client, db_session, admin):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.post(
        "/admin/users",
        headers=headers,
        json={
            "full_name": "Second Administrator",
            "email": "admin2@example.com",
            "department": "Administration",
            "password": "SecondAdminPass123!",
            "role": "admin",
        },
    )

    assert response.status_code == 201
    created_user = db_session.query(User).filter(
        User.email == "admin2@example.com"
    ).one()
    assert created_user.role == "admin"
    assert created_user.department == "Administration"

    log = db_session.query(AdminActivityLog).filter(
        AdminActivityLog.action == "admin_created"
    ).one()
    assert log.actor_user_id == admin.id
    assert log.target_user_id == created_user.id


def test_admin_rejects_duplicate_email_case_insensitively(
    client, admin, examiner
):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.post(
        "/admin/users",
        headers=headers,
        json={
            "full_name": "Duplicate Examiner",
            "email": "EXAMINER@example.com",
            "password": "AnotherPass123!",
            "role": "examiner",
        },
    )
    assert response.status_code == 409


def test_admin_can_list_users_with_departments(client, admin, examiner):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.get("/admin/users", headers=headers)
    assert response.status_code == 200
    examiner_data = next(
        item for item in response.json() if item["id"] == examiner.id
    )
    assert "department" in examiner_data


def test_admin_can_view_dashboard_statistics(client, admin):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.get("/admin/dashboard", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["total_admins"] == 1
    assert data["total_users"] == 1
    assert "total_sessions" in data


def test_admin_can_view_audit_logs(client, db_session, admin, student):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.patch(
        f"/admin/users/{student.id}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 200

    logs_response = client.get("/admin/activity-logs", headers=headers)
    assert logs_response.status_code == 200
    logs = logs_response.json()
    assert len(logs) == 1
    assert logs[0]["action"] == "user_deactivated"
    assert logs[0]["actor_name"] == admin.full_name
    assert logs[0]["target_name"] == student.full_name


def test_admin_can_deactivate_and_reactivate_examiner(
    client, db_session, admin, examiner
):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")

    response = client.patch(
        f"/admin/users/{examiner.id}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 200
    db_session.refresh(examiner)
    assert examiner.is_active is False

    response = client.patch(
        f"/admin/users/{examiner.id}/status",
        headers=headers,
        json={"is_active": True},
    )
    assert response.status_code == 200
    db_session.refresh(examiner)
    assert examiner.is_active is True

    actions = db_session.query(AdminActivityLog.action).filter(
        AdminActivityLog.target_user_id == examiner.id
    ).all()
    assert {item[0] for item in actions} == {
        "user_deactivated",
        "user_activated",
    }


def test_admin_cannot_deactivate_self(client, admin):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.patch(
        f"/admin/users/{admin.id}/status",
        headers=headers,
        json={"is_active": False},
    )
    assert response.status_code == 400


def test_admin_cannot_delete_self(client, admin):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.delete(
        f"/admin/users/{admin.id}",
        headers=headers,
    )
    assert response.status_code == 400


def test_admin_cannot_delete_last_active_admin(client, admin):
    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.delete(
        f"/admin/users/{admin.id}",
        headers=headers,
    )
    assert response.status_code == 400


def test_student_cannot_access_admin_endpoints(client, student):
    headers = get_auth_headers(client, student.email, "StudentPass123!")
    for path in ("/admin/users", "/admin/dashboard", "/admin/activity-logs"):
        response = client.get(path, headers=headers)
        assert response.status_code == 403


def test_examiner_cannot_create_users(client, examiner):
    headers = get_auth_headers(client, examiner.email, "ExaminerPass123!")
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
