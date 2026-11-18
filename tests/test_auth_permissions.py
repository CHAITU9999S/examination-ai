from app.models import User
from app.auth import hash_password

def test_public_registration_always_creates_student(client):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Test Admin",
            "email": "public_registration@test.com",
            "password": "TestPassword123",
            "role": "admin"
        }
    )

    assert response.status_code == 201
    assert response.json()["role"] == "student"


def test_public_registration_cannot_create_examiner(client):
    response = client.post(
        "/auth/register",
        json={
            "full_name": "Test Examiner",
            "email": "public_examiner@test.com",
            "password": "TestPassword123",
            "role": "examiner"
        }
    )

    assert response.status_code == 201
    assert response.json()["role"] == "student"


def test_student_cannot_create_examiner(client, db_session):
    student = User(
        full_name="Test Student",
        email="student_admin_test@test.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True
    )
    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    from app.auth import create_access_token

    token = create_access_token({"sub": str(student.id)})

    response = client.post(
        "/admin/users",
        json={
            "full_name": "New Examiner",
            "email": "new_examiner@test.com",
            "password": "TestPassword123",
            "role": "examiner",
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403



def test_valid_user_can_login(client, db_session):
    user = User(
        full_name="Login Student",
        email="login_student@test.com",
        password_hash=hash_password("TestPassword123"),
        role="student",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={
            "email": "login_student@test.com",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 200
    assert "access_token" in response.json()
    assert response.json()["token_type"] == "bearer"


def test_wrong_password_cannot_login(client, db_session):
    user = User(
        full_name="Wrong Password Student",
        email="wrong_password@test.com",
        password_hash=hash_password("TestPassword123"),
        role="student",
        is_active=True
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={
            "email": "wrong_password@test.com",
            "password": "WrongPassword123"
        }
    )

    assert response.status_code == 401


def test_inactive_user_cannot_login(client, db_session):
    user = User(
        full_name="Inactive Student",
        email="inactive_student@test.com",
        password_hash=hash_password("TestPassword123"),
        role="student",
        is_active=False
    )
    db_session.add(user)
    db_session.commit()

    response = client.post(
        "/auth/login",
        json={
            "email": "inactive_student@test.com",
            "password": "TestPassword123"
        }
    )

    assert response.status_code == 403
    
