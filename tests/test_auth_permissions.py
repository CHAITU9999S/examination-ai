from app.models import User


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

    assert response.status_code == 200
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

    assert response.status_code == 200
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
        "/auth/create-examiner",
        json={
            "full_name": "New Examiner",
            "email": "new_examiner@test.com",
            "password": "TestPassword123"
        },
        headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403
  
