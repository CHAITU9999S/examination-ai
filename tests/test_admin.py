import pytest
from datetime import datetime, timedelta

from app.auth import hash_password, verify_password
from app.models import (
    AdminActivityLog, Answer, AnswerMarkRevision, Exam, ExamAssignment,
    ExamQuestion, ExamSession, Option, PlatformSetting, QuestionBank, Result, User,
)


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


def test_admin_can_delete_all_questions_once_and_preserve_result_history(
    client, db_session, admin, student
):
    question = QuestionBank(
        question_text="What is 2 + 2?",
        question_type="MCQ",
        difficulty="easy",
        marks=1,
        created_by=admin.id,
    )
    db_session.add(question)
    db_session.flush()
    option = Option(question_id=question.id, option_text="4", is_correct=True)
    exam = Exam(
        title="History preservation exam",
        subject="Mathematics",
        duration_minutes=30,
        created_by=admin.id,
    )
    db_session.add_all([option, exam])
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id))
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=None,
        submitted_at=None,
        status="submitted",
        expires_at=datetime.utcnow() + timedelta(hours=1),
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.flush()
    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="4",
        awarded_marks=1,
    )
    db_session.add(answer)
    db_session.flush()
    result = Result(
        session_id=session.id,
        total_marks=1,
        obtained_marks=1,
        percentage=100,
        is_published=True,
    )
    db_session.add(result)
    db_session.commit()

    db_session.add(PlatformSetting(
        setting_key="all_questions_deleted_once",
        setting_value="false",
    ))
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    status_response = client.get("/admin/questions/reset-status", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["available"] is True

    response = client.delete("/admin/questions/all", headers=headers)
    assert response.status_code == 200
    assert db_session.query(QuestionBank).count() == 0
    assert db_session.query(Option).count() == 0
    assert db_session.query(ExamQuestion).count() == 0
    assert db_session.query(Answer).count() == 0
    assert db_session.query(ExamSession).filter(ExamSession.id == session.id).count() == 1
    assert db_session.query(Result).filter(Result.id == result.id).count() == 1

    status_response = client.get("/admin/questions/reset-status", headers=headers)
    assert status_response.status_code == 200
    assert status_response.json()["available"] is False

    second_response = client.delete("/admin/questions/all", headers=headers)
    assert second_response.status_code == 409


def test_student_cannot_use_global_question_deletion(client, student):
    headers = get_auth_headers(client, student.email, "StudentPass123!")
    response = client.delete("/admin/questions/all", headers=headers)
    assert response.status_code == 403


def test_deleting_student_preserves_completed_attempt_and_allows_later_cleanup(
    client, db_session, admin, student
):
    exam = Exam(
        title="Admin-owned examination",
        subject="Mathematics",
        duration_minutes=30,
        created_by=admin.id,
    )
    question = QuestionBank(
        question_text="A question owned by the Admin",
        question_type="MCQ",
        difficulty="easy",
        marks=2,
        created_by=admin.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add_all([
        ExamQuestion(exam_id=exam.id, question_id=question.id),
        ExamAssignment(exam_id=exam.id, student_id=student.id, assigned_by=admin.id, is_active=True),
    ])
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="submitted",
        started_at=datetime.utcnow() - timedelta(minutes=10),
        submitted_at=datetime.utcnow(),
        expires_at=datetime.utcnow(),
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.flush()
    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="A",
        awarded_marks=1,
        examiner_feedback="Good answer",
    )
    db_session.add(answer)
    db_session.flush()
    result = Result(
        session_id=session.id,
        total_marks=2,
        obtained_marks=1,
        percentage=50,
        is_published=True,
    )
    db_session.add(result)
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.delete(f"/admin/users/{student.id}", headers=headers)
    assert response.status_code == 200

    db_session.refresh(student)
    assert student.is_deleted is True
    assert student.is_active is False
    assert db_session.query(Exam).filter(Exam.id == exam.id).count() == 1
    assert db_session.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).count() == 1
    assert db_session.query(ExamSession).filter(ExamSession.id == session.id).count() == 1
    assert db_session.query(Answer).filter(Answer.id == answer.id).count() == 1
    assert db_session.query(Result).filter(Result.id == result.id).count() == 1

    retained_response = client.get("/admin/retained-data", headers=headers)
    assert retained_response.status_code == 200
    assert any(
        item["kind"] == "completed_submission" and item["id"] == session.id
        for item in retained_response.json()["items"]
    )

    cleanup_response = client.delete(
        f"/admin/retained-data/completed_submission/{session.id}",
        headers=headers,
    )
    assert cleanup_response.status_code == 200
    assert db_session.query(ExamSession).filter(ExamSession.id == session.id).count() == 0
    assert db_session.query(Answer).filter(Answer.id == answer.id).count() == 0
    assert db_session.query(Result).filter(Result.id == result.id).count() == 0
    assert db_session.query(Exam).filter(Exam.id == exam.id).count() == 1


def test_deleting_examiner_preserves_owned_completed_exam_and_question_for_later_deletion(
    client, db_session, admin, examiner, student
):
    exam = Exam(
        title="Examiner-owned completed exam",
        subject="Science",
        duration_minutes=25,
        created_by=examiner.id,
    )
    question = QuestionBank(
        question_text="Explain gravity",
        question_type="short_answer",
        difficulty="easy",
        marks=2,
        created_by=examiner.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id))
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="submitted",
        started_at=datetime.utcnow() - timedelta(minutes=10),
        submitted_at=datetime.utcnow(),
        expires_at=datetime.utcnow(),
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.flush()
    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="Gravity attracts objects.",
        awarded_marks=2,
    )
    db_session.add(answer)
    db_session.flush()
    result = Result(
        session_id=session.id,
        total_marks=2,
        obtained_marks=2,
        percentage=100,
        is_published=True,
    )
    revision = AnswerMarkRevision(
        answer_id=answer.id,
        revision_number=1,
        previous_marks=None,
        new_marks=2,
        revised_by=examiner.id,
    )
    db_session.add_all([result, revision])
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.delete(
        f"/admin/users/{examiner.id}/with-records",
        headers=headers,
    )
    assert response.status_code == 200

    db_session.refresh(examiner)
    assert examiner.is_deleted is True
    assert db_session.query(Exam).filter(Exam.id == exam.id).count() == 1
    assert db_session.query(ExamSession).filter(ExamSession.id == session.id).count() == 1
    assert db_session.query(Result).filter(Result.session_id == session.id).count() == 1
    assert db_session.query(AnswerMarkRevision).filter(
        AnswerMarkRevision.id == revision.id
    ).count() == 1
    assert db_session.query(QuestionBank).filter(
        QuestionBank.id == question.id
    ).one().created_by == examiner.id

    retained = client.get("/admin/retained-data", headers=headers)
    assert retained.status_code == 200
    retained_items = retained.json()["items"]
    assert any(item["kind"] == "completed_exam" and item["id"] == exam.id for item in retained_items)
    assert any(item["kind"] == "retained_question" and item["id"] == question.id for item in retained_items)
    assert any(item["kind"] == "answer_mark_revision" and item["id"] == revision.id for item in retained_items)

    delete_exam = client.delete(
        f"/admin/retained-data/completed_exam/{exam.id}",
        headers=headers,
    )
    assert delete_exam.status_code == 200
    assert db_session.query(Exam).filter(Exam.id == exam.id).count() == 0
    assert db_session.query(ExamSession).filter(ExamSession.id == session.id).count() == 0
    assert db_session.query(AnswerMarkRevision).filter(
        AnswerMarkRevision.id == revision.id
    ).count() == 0

    delete_question = client.delete(
        f"/admin/retained-data/retained_question/{question.id}",
        headers=headers,
    )
    assert delete_question.status_code == 200
    assert db_session.query(QuestionBank).filter(QuestionBank.id == question.id).count() == 0



def test_deleting_another_admin_preserves_completed_exam_and_grading_history(
    client, db_session, admin, student
):
    other_admin = User(
        full_name="Second Administrator",
        email="second-admin@example.com",
        password_hash=hash_password("SecondAdminPass123!"),
        role="admin",
        is_active=True,
    )
    db_session.add(other_admin)
    db_session.commit()
    db_session.refresh(other_admin)

    exam = Exam(
        title="Second Admin completed exam",
        subject="Physics",
        duration_minutes=20,
        created_by=other_admin.id,
    )
    question = QuestionBank(
        question_text="Define force",
        question_type="short_answer",
        difficulty="easy",
        marks=2,
        created_by=other_admin.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id))
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="submitted",
        started_at=datetime.utcnow() - timedelta(minutes=5),
        submitted_at=datetime.utcnow(),
        expires_at=datetime.utcnow(),
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.flush()
    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="A push or pull",
        awarded_marks=2,
    )
    db_session.add(answer)
    db_session.flush()
    revision = AnswerMarkRevision(
        answer_id=answer.id,
        revision_number=1,
        previous_marks=None,
        new_marks=2,
        revised_by=other_admin.id,
    )
    db_session.add(revision)
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.delete(
        f"/admin/users/{other_admin.id}",
        headers=headers,
    )
    assert response.status_code == 200

    db_session.refresh(other_admin)
    assert other_admin.is_deleted is True
    assert other_admin.is_active is False
    assert db_session.query(Exam).filter(Exam.id == exam.id).count() == 1
    assert db_session.query(ExamSession).filter(ExamSession.id == session.id).count() == 1
    assert db_session.query(Answer).filter(Answer.id == answer.id).count() == 1
    assert db_session.query(AnswerMarkRevision).filter(
        AnswerMarkRevision.id == revision.id
    ).count() == 1

    retained = client.get("/admin/retained-data", headers=headers)
    assert retained.status_code == 200
    assert any(
        item["kind"] == "completed_exam" and item["id"] == exam.id
        for item in retained.json()["items"]
    )
    assert any(
        item["kind"] == "answer_mark_revision" and item["id"] == revision.id
        for item in retained.json()["items"]
    )

def test_admin_performance_lists_students_and_their_completed_attempt_details(
    client, db_session, admin, student
):
    question = QuestionBank(
        question_text="Explain gravity.",
        question_type="long_answer",
        difficulty="easy",
        marks=5,
        expected_answer="Gravity is an attractive force.",
        created_by=admin.id,
    )
    db_session.add(question)
    db_session.flush()
    exam = Exam(
        title="Student history examination",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=datetime.utcnow() - timedelta(days=2),
        end_time=datetime.utcnow() - timedelta(days=2) + timedelta(hours=1),
        created_by=admin.id,
    )
    db_session.add(exam)
    db_session.flush()
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=admin.id,
        is_active=True,
    ))
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="submitted",
        started_at=datetime.utcnow() - timedelta(days=2),
        submitted_at=datetime.utcnow() - timedelta(days=2) + timedelta(minutes=25),
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="Gravity attracts objects.",
        awarded_marks=3,
    ))
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.get("/admin/performance", headers=headers)

    assert response.status_code == 200
    data = response.json()
    student_row = next(item for item in data["students"] if item["student_id"] == student.id)
    assert student_row["student_name"] == student.full_name
    assert len(student_row["attempts"]) == 1
    attempt = student_row["attempts"][0]
    assert attempt["session_id"] == session.id
    assert attempt["exam_title"] == exam.title
    assert attempt["creator_name"] == admin.full_name
    assert attempt["started_at"] is not None
    assert attempt["submitted_at"] is not None
    assert attempt["obtained_marks"] == 3
    assert attempt["total_marks"] == 5
    assert attempt["marks_status"] == "Evaluation in progress"



def test_student_performance_includes_assignments_from_all_staff_but_tracking_is_scoped(
    client, db_session, admin, examiner, student
):
    unassigned_student = User(
        full_name="Unassigned Student",
        email="unassigned.student@example.com",
        password_hash=hash_password("StudentPass123!"),
        role="student",
        is_active=True,
    )
    db_session.add(unassigned_student)
    db_session.flush()
    admin_exam = Exam(
        title="Admin-created examination",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=admin.id,
    )
    examiner_exam = Exam(
        title="Examiner-created examination",
        subject="Mathematics",
        duration_minutes=45,
        total_questions=1,
        created_by=examiner.id,
    )
    db_session.add_all([admin_exam, examiner_exam])
    db_session.flush()
    db_session.add_all([
        ExamAssignment(
            exam_id=admin_exam.id,
            student_id=student.id,
            assigned_by=admin.id,
            is_active=True,
        ),
        ExamAssignment(
            exam_id=examiner_exam.id,
            student_id=student.id,
            assigned_by=examiner.id,
            is_active=True,
        ),
    ])
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    tracking_response = client.get("/admin/performance", headers=headers)
    platform_response = client.get("/admin/student-performance", headers=headers)

    assert tracking_response.status_code == 200
    assert platform_response.status_code == 200

    tracking_students = {
        item["student_id"]: item for item in tracking_response.json()["students"]
    }
    platform_students = {
        item["student_id"]: item for item in platform_response.json()["students"]
    }
    tracking_student = tracking_students[student.id]
    platform_student = platform_students[student.id]
    assert unassigned_student.id not in tracking_students
    assert platform_students[unassigned_student.id]["total_assigned_examinations"] == 0

    assert tracking_student["total_assigned_examinations"] == 1
    assert [item["exam_title"] for item in tracking_student["attempts"]] == [
        admin_exam.title
    ]
    assert tracking_student["attempts"][0]["assigned_by_name"] == admin.full_name
    assert platform_student["total_assigned_examinations"] == 2
    platform_attempts = {item["exam_title"]: item for item in platform_student["attempts"]}
    assert set(platform_attempts) == {admin_exam.title, examiner_exam.title}
    assert platform_attempts[admin_exam.title]["assigned_by_name"] == admin.full_name
    assert platform_attempts[examiner_exam.title]["assigned_by_name"] == examiner.full_name




def test_global_student_performance_is_admin_only(client, examiner, student):
    examiner_headers = get_auth_headers(client, examiner.email, "ExaminerPass123!")
    student_headers = get_auth_headers(client, student.email, "StudentPass123!")

    examiner_response = client.get(
        "/admin/student-performance",
        headers=examiner_headers,
    )
    student_response = client.get(
        "/admin/student-performance",
        headers=student_headers,
    )

    assert examiner_response.status_code == 403
    assert student_response.status_code == 403



def test_admin_schedules_lists_only_future_examination_assignments(
    client, db_session, admin, student
):
    now = datetime.utcnow()
    future_exam = Exam(
        title="Upcoming examination",
        subject="Mathematics",
        duration_minutes=30,
        start_time=now + timedelta(days=2),
        end_time=now + timedelta(days=2, hours=1),
        created_by=admin.id,
    )
    past_exam = Exam(
        title="Past examination",
        subject="Mathematics",
        duration_minutes=30,
        start_time=now - timedelta(days=2),
        end_time=now - timedelta(days=2) + timedelta(hours=1),
        created_by=admin.id,
    )
    db_session.add_all([future_exam, past_exam])
    db_session.flush()
    db_session.add_all([
        ExamAssignment(exam_id=future_exam.id, student_id=student.id, assigned_by=admin.id, is_active=True),
        ExamAssignment(exam_id=past_exam.id, student_id=student.id, assigned_by=admin.id, is_active=True),
    ])
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.get("/admin/schedules", headers=headers)

    assert response.status_code == 200
    schedules = response.json()["schedules"]
    assert len(schedules) == 1
    assert schedules[0]["exam_id"] == future_exam.id
    assert schedules[0]["exam_title"] == future_exam.title

def test_examiner_activity_logs_include_examination_and_question_bank_changes(
    client, db_session, admin, examiner
):
    db_session.add_all([
        AdminActivityLog(
            actor_user_id=examiner.id,
            action="exam_question_added",
            details={"exam_id": 12, "question_id": 34},
        ),
        AdminActivityLog(
            actor_user_id=examiner.id,
            action="exam_question_bank_deleted",
            details={"exam_id": 12},
        ),
        AdminActivityLog(
            actor_user_id=examiner.id,
            action="question_added_to_bank",
            details={"bank_id": 56, "question_id": 78},
        ),
        AdminActivityLog(
            actor_user_id=examiner.id,
            action="question_updated_in_bank",
            details={"bank_id": 56, "question_id": 78},
        ),
        AdminActivityLog(
            actor_user_id=examiner.id,
            action="question_deleted_from_bank",
            details={"bank_id": 56, "question_id": 78},
        ),
        AdminActivityLog(
            actor_user_id=examiner.id,
            action="student_login",
            details={},
        ),
    ])
    db_session.commit()

    headers = get_auth_headers(client, admin.email, "AdminPass123!")
    response = client.get("/admin/examiner-activity-logs", headers=headers)

    assert response.status_code == 200
    actions = {item["action"] for item in response.json()}
    assert {
        "exam_question_added",
        "exam_question_bank_deleted",
        "question_added_to_bank",
        "question_updated_in_bank",
        "question_deleted_from_bank",
    }.issubset(actions)
    assert "student_login" not in actions

