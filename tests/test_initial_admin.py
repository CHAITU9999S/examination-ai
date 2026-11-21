import pytest

from app.auth import verify_password
from app.models import User
from scripts.create_initial_admin import create_initial_admin


def test_initial_admin_is_created_with_hashed_password(db_session):
    admin = create_initial_admin(
        db=db_session,
        full_name="First Administrator",
        email="FIRST.ADMIN@example.com",
        password="StrongAdminPass123!",
    )

    assert admin.id is not None
    assert admin.email == "first.admin@example.com"
    assert admin.role == "admin"
    assert admin.is_active is True
    assert admin.password_hash != "StrongAdminPass123!"
    assert verify_password(
        "StrongAdminPass123!",
        admin.password_hash,
    )


def test_initial_admin_creation_script_is_blocked_when_admin_exists(db_session):
    existing_admin = User(
        full_name="Existing Administrator",
        email="existing.admin@example.com",
        password_hash="already-hashed",
        role="admin",
        is_active=True,
    )
    db_session.add(existing_admin)
    db_session.commit()

    with pytest.raises(RuntimeError, match="Admin account already exists"):
        create_initial_admin(
            db=db_session,
            full_name="Second Administrator",
            email="second.admin@example.com",
            password="StrongAdminPass123!",
        )

    assert db_session.query(User).filter(
        User.role == "admin"
    ).count() == 1


@pytest.mark.parametrize(
    ("full_name", "email", "password"),
    [
        ("A", "valid@example.com", "StrongAdminPass123!"),
        ("Valid Admin", "invalid-email", "StrongAdminPass123!"),
        ("Valid Admin", "valid@example.com", "short"),
    ],
)
def test_initial_admin_rejects_invalid_input(
    db_session,
    full_name,
    email,
    password,
):
    with pytest.raises(ValueError):
        create_initial_admin(
            db=db_session,
            full_name=full_name,
            email=email,
            password=password,
        )

    assert db_session.query(User).filter(
        User.role == "admin"
    ).count() == 0


def test_bootstrap_endpoint_is_disabled_without_admin_bootstrap_secret(
    client,
    monkeypatch,
):
    monkeypatch.delenv("ADMIN_BOOTSTRAP_SECRET", raising=False)

    response = client.post(
        "/auth/bootstrap-admin",
        json={
            "full_name": "First Administrator",
            "email": "first.admin@example.com",
            "password": "StrongAdminPass123!",
        },
    )

    assert response.status_code == 404


def test_bootstrap_endpoint_rejects_invalid_admin_bootstrap_secret(
    client,
    monkeypatch,
):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", "a" * 40)

    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": "wrong-token"},
        json={
            "full_name": "First Administrator",
            "email": "first.admin@example.com",
            "password": "StrongAdminPass123!",
        },
    )

    assert response.status_code == 403


def test_bootstrap_endpoint_creates_admin_and_allows_login(
    client,
    db_session,
    monkeypatch,
):
    setup_secret = "test-admin-bootstrap-secret-" + ("x" * 40)
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", setup_secret)

    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": setup_secret},
        json={
            "full_name": "First Administrator",
            "email": "FIRST.ADMIN@example.com",
            "password": "StrongAdminPass123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    assert response.json()["email"] == "first.admin@example.com"

    admin = db_session.query(User).filter(
        User.email == "first.admin@example.com"
    ).one()
    assert verify_password(
        "StrongAdminPass123!",
        admin.password_hash,
    )

    login_response = client.post(
        "/auth/login",
        json={
            "email": "first.admin@example.com",
            "password": "StrongAdminPass123!",
        },
    )

    assert login_response.status_code == 200
    assert login_response.json()["token_type"] == "bearer"
    assert login_response.json()["access_token"]


def test_bootstrap_endpoint_allows_additional_admin_accounts(
    client,
    db_session,
    monkeypatch,
):
    setup_secret = "test-admin-bootstrap-secret-" + ("y" * 40)
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", setup_secret)

    existing_admin = User(
        full_name="Existing Administrator",
        email="existing.admin@example.com",
        password_hash="already-hashed",
        role="admin",
        is_active=True,
    )
    db_session.add(existing_admin)
    db_session.commit()

    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": setup_secret},
        json={
            "full_name": "Second Administrator",
            "email": "second.admin@example.com",
            "password": "StrongAdminPass123!",
        },
    )

    assert response.status_code == 201
    assert response.json()["role"] == "admin"
    assert db_session.query(User).filter(
        User.role == "admin"
    ).count() == 2
