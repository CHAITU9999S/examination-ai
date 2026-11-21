from datetime import datetime, timedelta, timezone

from app.auth import create_access_token
from app.models import User, Exam, ExamAssignment, ExamQuestion, ExamSession, QuestionBank


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


def test_exam_creator_can_update_question_marks_and_view_history(client, db_session):
    creator = create_user(db_session, "examiner", "marks_owner@test.com")
    exam = Exam(
        title="Marks Settings Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=2,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.flush()
    first = QuestionBank(
        question_text="Question one",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=2,
        created_by=creator.id,
    )
    second = QuestionBank(
        question_text="Question two",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=2,
        created_by=creator.id,
    )
    db_session.add_all([first, second])
    db_session.flush()
    db_session.add_all([
        ExamQuestion(exam_id=exam.id, question_id=first.id, question_order=1),
        ExamQuestion(exam_id=exam.id, question_id=second.id, question_order=2),
    ])
    db_session.commit()

    response = client.put(
        f"/exams/{exam.id}/question-marks",
        json={"marks_by_group": {"easy|MCQ": 3}},
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 200
    assert db_session.get(QuestionBank, first.id).marks == 3
    assert db_session.get(QuestionBank, second.id).marks == 3

    history = client.get(
        f"/exams/{exam.id}/question-marks",
        headers=get_auth_headers(creator),
    )
    assert history.status_code == 200
    assert history.json()["marks_by_group"]["easy|MCQ"] == 3
    assert history.json()["revisions_used"] == 1
    assert history.json()["revisions"][0]["marks_snapshot"]["easy|MCQ"] == 3


def test_question_paper_marks_have_a_separate_three_revision_limit(client, db_session):
    creator = create_user(db_session, "examiner", "marks_limit@test.com")
    exam = Exam(
        title="Marks Revision Limit",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.flush()
    question = QuestionBank(
        question_text="Question",
        question_type="short_answer",
        subject="Science",
        difficulty="medium",
        marks=1,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id, question_order=1))
    db_session.commit()

    for new_marks in (2, 3, 4):
        response = client.put(
            f"/exams/{exam.id}/question-marks",
            json={"marks_by_group": {"medium|short_answer": new_marks}},
            headers=get_auth_headers(creator),
        )
        assert response.status_code == 200

    fourth_change = client.put(
        f"/exams/{exam.id}/question-marks",
        json={"marks_by_group": {"medium|short_answer": 5}},
        headers=get_auth_headers(creator),
    )
    assert fourth_change.status_code == 409


def test_admin_cannot_change_another_creators_question_marks(client, db_session):
    creator = create_user(db_session, "examiner", "marks_creator@test.com")
    admin = create_user(db_session, "admin", "marks_admin@test.com")
    exam = Exam(
        title="Owned Marks Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.flush()
    question = QuestionBank(
        question_text="Question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id, question_order=1))
    db_session.commit()

    response = client.put(
        f"/exams/{exam.id}/question-marks",
        json={"marks_by_group": {"easy|MCQ": 2}},
        headers=get_auth_headers(admin),
    )
    assert response.status_code == 403


def test_question_marks_cannot_change_after_student_session(client, db_session):
    creator = create_user(db_session, "examiner", "marks_locked@test.com")
    student = create_user(db_session, "student", "marks_locked_student@test.com")
    exam = Exam(
        title="Started Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.flush()
    question = QuestionBank(
        question_text="Question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id, question_order=1))
    db_session.add(ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="in_progress",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None),
    ))
    db_session.commit()

    response = client.put(
        f"/exams/{exam.id}/question-marks",
        json={"marks_by_group": {"easy|MCQ": 2}},
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 409
    assert db_session.get(QuestionBank, question.id).marks == 1


def test_question_marks_cannot_change_question_shared_with_another_exam(client, db_session):
    creator = create_user(db_session, "examiner", "shared_marks@test.com")
    first_exam = Exam(
        title="First Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    second_exam = Exam(
        title="Second Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add_all([first_exam, second_exam])
    db_session.flush()
    question = QuestionBank(
        question_text="Shared Question",
        question_type="short_answer",
        subject="Science",
        difficulty="medium",
        marks=2,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add_all([
        ExamQuestion(exam_id=first_exam.id, question_id=question.id, question_order=1),
        ExamQuestion(exam_id=second_exam.id, question_id=question.id, question_order=1),
    ])
    db_session.commit()

    response = client.put(
        f"/exams/{first_exam.id}/question-marks",
        json={"marks_by_group": {"medium|short_answer": 3}},
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 409
    assert db_session.get(QuestionBank, question.id).marks == 2


def test_exam_creator_can_delete_whole_question_bank_safely(client, db_session):
    creator = create_user(db_session, "examiner", "whole_bank_owner@test.com")
    student = create_user(db_session, "student", "whole_bank_student@test.com")
    source = QuestionBank(
        question_text="Original question",
        question_type="short_answer",
        subject="Science",
        difficulty="easy",
        marks=2,
        created_by=creator.id,
    )
    db_session.add(source)
    db_session.flush()
    local_question = QuestionBank(
        question_text="Local question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    copied_question = QuestionBank(
        question_text="Copied question",
        question_type="short_answer",
        subject="Science",
        difficulty="easy",
        marks=2,
        created_by=creator.id,
        source_question_id=source.id,
    )
    exam = Exam(
        title="Delete Bank Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=2,
        created_by=creator.id,
    )
    db_session.add_all([local_question, copied_question, exam])
    db_session.flush()
    db_session.add_all([
        ExamQuestion(exam_id=exam.id, question_id=local_question.id, question_order=1),
        ExamQuestion(exam_id=exam.id, question_id=copied_question.id, question_order=2),
        ExamAssignment(exam_id=exam.id, student_id=student.id, assigned_by=creator.id, is_active=True),
    ])
    db_session.commit()

    response = client.delete(
        f"/exams/{exam.id}/question-bank",
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 200
    assert db_session.get(QuestionBank, local_question.id) is None
    assert db_session.get(QuestionBank, copied_question.id) is None
    assert db_session.get(QuestionBank, source.id) is not None
    assert db_session.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).count() == 0
    assignment = db_session.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam.id,
        ExamAssignment.student_id == student.id,
    ).one()
    assert assignment.is_active is False


def test_exam_question_bank_cannot_be_deleted_after_session(client, db_session):
    creator = create_user(db_session, "examiner", "whole_bank_locked@test.com")
    student = create_user(db_session, "student", "whole_bank_locked_student@test.com")
    exam = Exam(
        title="Locked Bank Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.flush()
    question = QuestionBank(
        question_text="Question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id, question_order=1))
    db_session.add(ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="in_progress",
        started_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=(datetime.now(timezone.utc) + timedelta(hours=1)).replace(tzinfo=None),
    ))
    db_session.commit()

    response = client.delete(
        f"/exams/{exam.id}/question-bank",
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 409
    assert db_session.get(QuestionBank, question.id) is not None


def test_exam_configuration_has_three_revisions(client, db_session):
    creator = create_user(db_session, "examiner", "config_revision_limit@test.com")
    exam_data = valid_exam_data()
    exam_data["total_questions"] = 1
    exam_data["selection_rules"] = {}
    create_response = client.post(
        "/exams/",
        json=exam_data,
        headers=get_auth_headers(creator),
    )
    assert create_response.status_code == 201
    exam_id = create_response.json()["exam_id"]

    question = QuestionBank(
        question_text="One question",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam_id, question_id=question.id, question_order=1))
    db_session.commit()

    for revision in range(1, 4):
        update_data = valid_exam_data()
        update_data["total_questions"] = 1
        update_data["selection_rules"] = {}
        update_data["title"] = f"Configuration revision {revision}"
        response = client.put(
            f"/exams/{exam_id}",
            json=update_data,
            headers=get_auth_headers(creator),
        )
        assert response.status_code == 200

    fourth_update = valid_exam_data()
    fourth_update["total_questions"] = 1
    fourth_update["selection_rules"] = {}
    response = client.put(
        f"/exams/{exam_id}",
        json=fourth_update,
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 409


def test_question_marks_revisions_do_not_use_exam_configuration_limit(client, db_session):
    creator = create_user(db_session, "examiner", "separate_revision_limits@test.com")
    exam_data = valid_exam_data()
    exam_data["total_questions"] = 1
    exam_data["selection_rules"] = {}
    create_response = client.post(
        "/exams/",
        json=exam_data,
        headers=get_auth_headers(creator),
    )
    exam_id = create_response.json()["exam_id"]
    question = QuestionBank(
        question_text="One question",
        question_type="MCQ",
        subject="General Knowledge",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    db_session.add(question)
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam_id, question_id=question.id, question_order=1))
    db_session.commit()

    for new_marks in (2, 3, 4):
        marks_response = client.put(
            f"/exams/{exam_id}/question-marks",
            json={"marks_by_group": {"easy|MCQ": new_marks}},
            headers=get_auth_headers(creator),
        )
        assert marks_response.status_code == 200

    update_data = valid_exam_data()
    update_data["total_questions"] = 1
    update_data["selection_rules"] = {}
    update_response = client.put(
        f"/exams/{exam_id}",
        json=update_data,
        headers=get_auth_headers(creator),
    )
    assert update_response.status_code == 200

    marks_history = client.get(
        f"/exams/{exam_id}/question-marks",
        headers=get_auth_headers(creator),
    )
    config_history = client.get(
        f"/exams/{exam_id}/configuration-revisions",
        headers=get_auth_headers(creator),
    )
    assert marks_history.json()["revisions_used"] == 3
    assert config_history.json()["revisions_used"] == 1
