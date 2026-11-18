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


def test_initial_admin_creation_is_blocked_when_admin_exists(db_session):
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
