from app.auth import verify_password
from app.models import User


SECRET = "test-only-secret-value-with-more-than-32-characters"


def payload(email):
    return {
        "full_name": "New Admin",
        "email": email,
        "password": "StrongPassword123!",
    }


def test_secret_endpoint_creates_admin_without_login(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", SECRET)
    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": SECRET},
        json=payload("first-new-admin@example.com"),
    )
    assert response.status_code == 201
    user = db_session.query(User).filter_by(email="first-new-admin@example.com").one()
    assert user.role == "admin"
    assert verify_password("StrongPassword123!", user.password_hash)


def test_secret_endpoint_allows_additional_admin(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", SECRET)
    db_session.add(User(
        full_name="Existing Admin",
        email="existing-admin@example.com",
        password_hash="existing-hash",
        role="admin",
        is_active=True,
    ))
    db_session.commit()
    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": SECRET},
        json=payload("second-new-admin@example.com"),
    )
    assert response.status_code == 201
    assert db_session.query(User).filter_by(role="admin").count() == 2


def test_secret_endpoint_rejects_invalid_secret(client, monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", SECRET)
    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": "wrong-secret"},
        json=payload("invalid-secret@example.com"),
    )
    assert response.status_code == 403


def test_secret_endpoint_rejects_duplicate_email(client, db_session, monkeypatch):
    monkeypatch.setenv("ADMIN_BOOTSTRAP_SECRET", SECRET)
    db_session.add(User(
        full_name="Existing Student",
        email="duplicate@example.com",
        password_hash="existing-hash",
        role="student",
        is_active=True,
    ))
    db_session.commit()
    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": SECRET},
        json=payload("DUPLICATE@example.com"),
    )
    assert response.status_code == 409


def test_secret_endpoint_is_disabled_when_secret_missing(client, monkeypatch):
    monkeypatch.delenv("ADMIN_BOOTSTRAP_SECRET", raising=False)
    response = client.post(
        "/auth/bootstrap-admin",
        headers={"X-Admin-Bootstrap-Token": SECRET},
        json=payload("disabled@example.com"),
    )
    assert response.status_code == 404
