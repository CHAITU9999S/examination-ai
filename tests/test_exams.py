from datetime import datetime, timedelta, timezone

from app.auth import create_access_token
from app.models import User, Exam, ExamAssignment, QuestionBank, ExamQuestion


def create_user(db, role, email):
    user = User(
        full_name=f"Test {role.title()}",
        email=email,
        password_hash="test-password-hash",
        role=role,
        is_active=True,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


def get_auth_headers(user):
    token = create_access_token({
        "sub": str(user.id)
    })

    return {
        "Authorization": f"Bearer {token}"
    }


def valid_exam_data():
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    end = start + timedelta(hours=2)

    return {
        "title": "General Knowledge Test",
        "subject": "General Knowledge",
        "duration_minutes": 60,
        "total_questions": 4,
        "randomize_questions": True,
        "selection_rules": {
            "difficulty_counts": {
                "easy": 2,
                "medium": 1,
                "hard": 1,
            },
            "question_type_counts": {
                "MCQ": 2,
                "short_answer": 1,
                "long_answer": 1,
            },
        },
        "start_time": start.isoformat(),
        "end_time": end.isoformat(),
        "negative_marking": True,
        "proctoring_enabled": True,
        "gaze_tracking_sensitivity": 0.65,
        "max_tab_switch_warnings": 3,
    }


def test_examiner_can_create_exam(client, db_session):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_create@test.com",
    )

    response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(examiner),
    )

    assert response.status_code == 201
    assert response.json()["message"] == "Exam created successfully"
    assert "exam_id" in response.json()


def test_admin_can_create_exam(client, db_session):
    admin = create_user(
        db_session,
        "admin",
        "admin_create_exam@test.com",
    )

    response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(admin),
    )

    assert response.status_code == 201


def test_exam_configuration_is_saved_and_returned(
    client,
    db_session,
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_list@test.com",
    )

    create_response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(examiner),
    )

    assert create_response.status_code == 201

    response = client.get(
        "/exams/",
        headers=get_auth_headers(examiner),
    )

    assert response.status_code == 200

    exam_id = create_response.json()["exam_id"]

    exam = next(
        item
        for item in response.json()
        if item["id"] == exam_id
    )

    assert exam["title"] == "General Knowledge Test"
    assert exam["subject"] == "General Knowledge"
    assert exam["duration_minutes"] == 60
    assert exam["total_questions"] == 4
    assert exam["randomize_questions"] is True
    assert exam["negative_marking"] is True
    assert exam["proctoring_enabled"] is True
    assert exam["gaze_tracking_sensitivity"] == 0.65
    assert exam["max_tab_switch_warnings"] == 3

    assert (
        exam["selection_rules"]["difficulty_counts"]["easy"]
        == 2
    )

    assert (
        exam["selection_rules"]["question_type_counts"]["MCQ"]
        == 2
    )


def test_rejects_incomplete_distribution_rules(
    client,
    db_session,
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_invalid_rules@test.com",
    )

    data = valid_exam_data()

    data["selection_rules"] = {
        "difficulty_counts": {
            "easy": 4,
        }
    }

    response = client.post(
        "/exams/",
        json=data,
        headers=get_auth_headers(examiner),
    )

    assert response.status_code == 400


def test_rejects_invalid_gaze_sensitivity(
    client,
    db_session,
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_gaze@test.com",
    )

    data = valid_exam_data()
    data["gaze_tracking_sensitivity"] = 1.5

    response = client.post(
        "/exams/",
        json=data,
        headers=get_auth_headers(examiner),
    )

    assert response.status_code == 422


def test_rejects_negative_tab_switch_warnings(
    client,
    db_session,
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_warnings@test.com",
    )

    data = valid_exam_data()
    data["max_tab_switch_warnings"] = -1

    response = client.post(
        "/exams/",
        json=data,
        headers=get_auth_headers(examiner),
    )

    assert response.status_code == 422


def test_student_cannot_create_exam(client, db_session):
    student = create_user(
        db_session,
        "student",
        "student_create_exam@test.com",
    )

    response = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(student),
    )

    assert response.status_code == 403


def test_student_can_list_available_exams(client, db_session):
    student = create_user(
        db_session,
        "student",
        "student_list_exams@test.com",
    )
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_student_list@test.com",
    )
    exam = Exam(
        title="Student Visible Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=5,
        start_time=datetime.now(timezone.utc) - timedelta(minutes=1),
        end_time=datetime.now(timezone.utc) + timedelta(hours=1),
        created_by=examiner.id,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=examiner.id,
        is_active=True,
    ))
    db_session.commit()

    response = client.get(
        "/exams/",
        headers=get_auth_headers(student),
    )

    assert response.status_code == 200
    exams = response.json()
    visible_exam = next(item for item in exams if item["id"] == exam.id)
    assert visible_exam["title"] == "Student Visible Exam"
    assert "options" not in visible_exam
    assert "answers" not in visible_exam


def test_examiner_cannot_list_another_examiners_exams(
    client,
    db_session,
):
    first_examiner = create_user(
        db_session,
        "examiner",
        "first_examiner@test.com",
    )

    second_examiner = create_user(
        db_session,
        "examiner",
        "second_examiner@test.com",
    )

    exam = Exam(
        title="Private Examiner Exam",
        subject="Mathematics",
        duration_minutes=60,
        total_questions=4,
        created_by=first_examiner.id,
    )

    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    response = client.get(
        "/exams/",
        headers=get_auth_headers(second_examiner),
    )

    assert response.status_code == 200

    returned_ids = [
        item["id"]
        for item in response.json()
    ]

    assert exam.id not in returned_ids


def test_admin_can_list_exams_created_by_examiners(
    client,
    db_session,
):
    examiner = create_user(
        db_session,
        "examiner",
        "examiner_admin_visibility@test.com",
    )

    admin = create_user(
        db_session,
        "admin",
        "admin_exam_visibility@test.com",
    )

    exam = Exam(
        title="Examiner Created Exam",
        subject="Science",
        duration_minutes=45,
        total_questions=3,
        created_by=examiner.id,
    )

    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    response = client.get(
        "/exams/",
        headers=get_auth_headers(admin),
    )

    assert response.status_code == 200

    returned_ids = [
        item["id"]
        for item in response.json()
    ]

    assert exam.id in returned_ids

def test_admin_and_other_examiner_cannot_edit_an_exam_they_do_not_own(
    client,
    db_session,
):
    owner = create_user(
        db_session,
        "examiner",
        "assignment_owner@test.com",
    )
    admin = create_user(
        db_session,
        "admin",
        "assignment_admin@test.com",
    )
    other_examiner = create_user(
        db_session,
        "examiner",
        "assignment_other@test.com",
    )
    exam = Exam(
        title="Creator-Owned Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=owner.id,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    for user in (admin, other_examiner):
        response = client.put(
            f"/exams/{exam.id}/questions",
            json=[1],
            headers=get_auth_headers(user),
        )
        assert response.status_code == 403
        assert response.json()["detail"] == (
            "Only the examination creator can change its question assignments."
        )

def test_exam_creator_can_add_question_to_own_exam_bank(
    client,
    db_session,
):
    creator = create_user(
        db_session,
        "examiner",
        "bank_add_creator@test.com",
    )
    exam = Exam(
        title="Bank Management Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    response = client.post(
        f"/exams/{exam.id}/questions",
        json={
            "question_text": "Explain photosynthesis.",
            "question_type": "short_answer",
            "subject": "Science",
            "difficulty": "easy",
            "marks": 5,
            "expected_answer": "Plants make food using light.",
        },
        headers=get_auth_headers(creator),
    )

    assert response.status_code == 201
    question_id = response.json()["question_id"]
    assert db_session.query(QuestionBank).filter(
        QuestionBank.id == question_id
    ).first() is not None
    assert db_session.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id,
        ExamQuestion.question_id == question_id,
    ).first() is not None


def test_exam_creator_can_remove_question_without_deleting_original(
    client,
    db_session,
):
    creator = create_user(
        db_session,
        "examiner",
        "bank_remove_creator@test.com",
    )
    source_question = QuestionBank(
        question_text="What is gravity?",
        question_type="short_answer",
        subject="Science",
        difficulty="easy",
        marks=5,
        created_by=creator.id,
    )
    db_session.add(source_question)
    db_session.flush()
    exam = Exam(
        title="Question Removal Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.flush()
    db_session.add(ExamQuestion(
        exam_id=exam.id,
        question_id=source_question.id,
        question_order=1,
    ))
    db_session.commit()
    db_session.refresh(exam)
    db_session.refresh(source_question)

    response = client.delete(
        f"/exams/{exam.id}/questions/{source_question.id}",
        headers=get_auth_headers(creator),
    )

    assert response.status_code == 200
    assert db_session.query(QuestionBank).filter(
        QuestionBank.id == source_question.id
    ).first() is not None
    assert db_session.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id,
        ExamQuestion.question_id == source_question.id,
    ).first() is None


def test_non_creator_cannot_add_question_to_exam_bank(
    client,
    db_session,
):
    creator = create_user(
        db_session,
        "examiner",
        "bank_owner@test.com",
    )
    admin = create_user(
        db_session,
        "admin",
        "bank_non_owner_admin@test.com",
    )
    exam = Exam(
        title="Protected Question Bank",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    response = client.post(
        f"/exams/{exam.id}/questions",
        json={
            "question_text": "Explain photosynthesis.",
            "question_type": "short_answer",
            "subject": "Science",
            "difficulty": "easy",
            "marks": 5,
        },
        headers=get_auth_headers(admin),
    )
    assert response.status_code == 403
