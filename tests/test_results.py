from datetime import datetime, timedelta

from app.auth import hash_password
from app.models import Exam, ExamSession, Result, User


def create_user(db_session, email, role="student"):
    user = User(
        full_name=f"Test {role.title()}",
        email=email,
        password_hash=hash_password("TestPassword123!"),
        role=role,
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def create_published_result(db_session, student, exam, score=8.0, published=True):
    now = datetime.utcnow()
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now - timedelta(minutes=30),
        submitted_at=now - timedelta(minutes=1),
        expires_at=now,
        status="submitted",
        selected_question_ids=[],
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    result = Result(
        session_id=session.id,
        total_marks=10.0,
        obtained_marks=score,
        percentage=score * 10,
        question_scores=[],
        evaluated_at=now,
        is_published=published,
        published_at=now if published else None,
    )
    db_session.add(result)
    db_session.commit()
    db_session.refresh(result)
    return session, result


def login_headers(client, email):
    response = client.post(
        "/auth/login",
        json={
            "email": email,
            "password": "TestPassword123!",
        },
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_student_can_list_only_published_results(client, db_session):
    student = create_user(db_session, "results-student@example.com")
    exam = Exam(
        title="Published Results Test",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    create_published_result(db_session, student, exam, score=8, published=True)
    create_published_result(db_session, student, exam, score=5, published=False)

    response = client.get(
        "/results/me",
        headers=login_headers(client, student.email),
    )

    assert response.status_code == 200
    results = response.json()["results"]
    assert len(results) == 1
    assert results[0]["exam_title"] == exam.title
    assert results[0]["obtained_marks"] == 8
    assert results[0]["percentile"] == 100


def test_student_can_open_own_published_result(client, db_session):
    student = create_user(db_session, "result-detail-student@example.com")
    exam = Exam(
        title="Result Detail Test",
        subject="Mathematics",
        duration_minutes=45,
        total_questions=1,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    session, result = create_published_result(
        db_session,
        student,
        exam,
        score=7.5,
        published=True,
    )

    response = client.get(
        f"/results/{session.id}",
        headers=login_headers(client, student.email),
    )

    assert response.status_code == 200
    data = response.json()
    assert data["result_id"] == result.id
    assert data["obtained_marks"] == 7.5
    assert data["percentage"] == 75


def test_student_cannot_view_another_students_result(client, db_session):
    owner = create_user(db_session, "result-owner@example.com")
    other_student = create_user(db_session, "result-other@example.com")
    exam = Exam(
        title="Private Result Test",
        duration_minutes=30,
        total_questions=1,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    session, _ = create_published_result(
        db_session,
        owner,
        exam,
        published=True,
    )

    response = client.get(
        f"/results/{session.id}",
        headers=login_headers(client, other_student.email),
    )

    assert response.status_code == 403


def test_student_cannot_open_unpublished_result(client, db_session):
    student = create_user(db_session, "unpublished-result@example.com")
    exam = Exam(
        title="Unpublished Result Test",
        duration_minutes=30,
        total_questions=1,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    session, _ = create_published_result(
        db_session,
        student,
        exam,
        published=False,
    )

    response = client.get(
        f"/results/{session.id}",
        headers=login_headers(client, student.email),
    )

    assert response.status_code == 404
