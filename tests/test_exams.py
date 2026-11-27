from datetime import datetime, timedelta, timezone

from app.auth import create_access_token
from app.models import User, Exam, ExamAssignment, ExamQuestion, ExamSession, QuestionBank, Option
from app.question_bank_models import QuestionCollection, QuestionCollectionItem


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



def test_student_overview_returns_creator_and_assigner_and_only_own_assignments(
    client, db_session
):
    creator = create_user(db_session, "examiner", "overview_creator@test.com")
    student = create_user(db_session, "student", "overview_student@test.com")
    other_student = create_user(db_session, "student", "overview_other@test.com")
    start = datetime.now(timezone.utc) + timedelta(hours=1)
    exam = Exam(
        title="Student overview attribution test",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        randomize_questions=False,
        selection_rules={"instructions": ["Read each question carefully."]},
        start_time=start,
        end_time=start + timedelta(hours=2),
        negative_marking=True,
        created_by=creator.id,
    )
    question = QuestionBank(
        question_text="What is gravity?",
        question_type="MCQ",
        difficulty="easy",
        marks=5,
        negative_marks=1,
        created_by=creator.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add(ExamQuestion(
        exam_id=exam.id,
        question_id=question.id,
        question_order=1,
    ))
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=creator.id,
        is_active=True,
    ))
    db_session.commit()

    response = client.get(
        "/exams/student-overview",
        headers=get_auth_headers(student),
    )
    list_response = client.get(
        "/exams",
        headers=get_auth_headers(student),
    )
    other_response = client.get(
        "/exams/student-overview",
        headers=get_auth_headers(other_student),
    )

    assert response.status_code == 200
    items = response.json()["examinations"]
    assert len(items) == 1
    assert items[0]["title"] == exam.title
    assert items[0]["creator_name"] == creator.full_name
    assert items[0]["assigned_by_name"] == creator.full_name
    assert list_response.status_code == 200
    listed_exam = next(item for item in list_response.json() if item["id"] == exam.id)
    assert listed_exam["created_by_name"] == creator.full_name
    assert listed_exam["assigned_by_name"] == creator.full_name
    assert items[0]["category"] == "available"
    assert items[0]["can_start"] is False
    assert items[0]["question_breakdown"][0]["count"] == 1
    assert items[0]["instructions"] == ["Read each question carefully."]
    assert other_response.status_code == 200
    assert other_response.json()["examinations"] == []




def test_expired_student_session_is_not_reported_as_completed(
    client, db_session
):
    examiner = create_user(db_session, "examiner", "expired_owner@test.com")
    student = create_user(db_session, "student", "expired_student@test.com")
    unattempted_student = create_user(db_session, "student", "expired_unattempted@test.com")
    paused_student = create_user(db_session, "student", "expired_paused@test.com")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam = Exam(
        title="Expired session status test",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(hours=1),
        created_by=examiner.id,
    )
    db_session.add(exam)
    db_session.flush()
    db_session.add_all([
        ExamAssignment(
            exam_id=exam.id,
            student_id=student.id,
            assigned_by=examiner.id,
            is_active=True,
        ),
        ExamAssignment(
            exam_id=exam.id,
            student_id=unattempted_student.id,
            assigned_by=examiner.id,
            is_active=True,
        ),
        ExamAssignment(
            exam_id=exam.id,
            student_id=paused_student.id,
            assigned_by=examiner.id,
            is_active=True,
        ),
    ])
    db_session.add_all([
        ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        status="expired",
        ),
        ExamSession(
            exam_id=exam.id,
            student_id=paused_student.id,
            started_at=now - timedelta(minutes=20),
            expires_at=now + timedelta(minutes=20),
            status="in_progress",
            is_paused=True,
            paused_at=now - timedelta(minutes=10),
        ),
    ])
    db_session.commit()

    headers = get_auth_headers(examiner)
    assignments_response = client.get(
        f"/exams/{exam.id}/assignments",
        headers=headers,
    )
    exams_response = client.get("/exams?mine=true", headers=headers)
    performance_response = client.get("/admin/performance", headers=headers)

    assert assignments_response.status_code == 200
    assignment_statuses = {
        item["student_id"]: item["student_exam_status"]
        for item in assignments_response.json()["students"]
    }
    assert assignment_statuses[student.id] == "expired"
    assert assignment_statuses[unattempted_student.id] == "expired"
    assert assignment_statuses[paused_student.id] == "expired"
    assert exams_response.status_code == 200
    assert performance_response.status_code == 200
    performance_students = {
        item["student_id"]: item
        for item in performance_response.json()["students"]
    }
    unattempted_attempt = performance_students[unattempted_student.id]["attempts"][0]
    paused_attempt = performance_students[paused_student.id]["attempts"][0]
    assert unattempted_attempt["status_label"] == "Expired"
    assert unattempted_attempt["is_started"] is False
    assert unattempted_attempt["is_taken"] is False
    assert paused_attempt["status_label"] == "Expired"
    assert paused_attempt["is_started"] is True
    assert paused_attempt["is_taken"] is True
    exam_row = exams_response.json()[0]
    assert exam_row["completed_session_count"] == 0
    assert exam_row["expired_session_count"] == 1




def test_student_overview_distinguishes_paused_pending_from_active_in_progress(
    client, db_session
):
    creator = create_user(db_session, "examiner", "pending_creator@test.com")
    paused_student = create_user(db_session, "student", "pending_paused@test.com")
    active_student = create_user(db_session, "student", "pending_active@test.com")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam = Exam(
        title="Paused versus active status test",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=now - timedelta(minutes=30),
        end_time=now + timedelta(minutes=30),
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.flush()
    db_session.add_all([
        ExamAssignment(
            exam_id=exam.id,
            student_id=paused_student.id,
            assigned_by=creator.id,
            is_active=True,
        ),
        ExamAssignment(
            exam_id=exam.id,
            student_id=active_student.id,
            assigned_by=creator.id,
            is_active=True,
        ),
        ExamSession(
            exam_id=exam.id,
            student_id=paused_student.id,
            started_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(minutes=25),
            status="in_progress",
            is_paused=True,
            paused_at=now - timedelta(minutes=1),
        ),
        ExamSession(
            exam_id=exam.id,
            student_id=active_student.id,
            started_at=now - timedelta(minutes=5),
            expires_at=now + timedelta(minutes=25),
            status="in_progress",
            is_paused=False,
        ),
    ])
    db_session.commit()

    paused_response = client.get(
        "/exams/student-overview",
        headers=get_auth_headers(paused_student),
    )
    active_response = client.get(
        "/exams/student-overview",
        headers=get_auth_headers(active_student),
    )

    assert paused_response.status_code == 200
    assert active_response.status_code == 200
    paused_exam = paused_response.json()["examinations"][0]
    active_exam = active_response.json()["examinations"][0]
    assert paused_exam["is_pending"] is True
    assert paused_exam["is_in_progress"] is False
    assert paused_exam["is_paused"] is True
    assert active_exam["is_pending"] is False
    assert active_exam["is_in_progress"] is True
    assert active_exam["is_paused"] is False



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

    admin_assignments = client.get(
        f"/exams/{exam.id}/assignments",
        headers=get_auth_headers(admin),
    )
    assert admin_assignments.status_code == 200
    assert admin_assignments.json()["exam_id"] == exam.id

    examiner_assignments = client.get(
        f"/exams/{exam.id}/assignments",
        headers=get_auth_headers(other_examiner),
    )
    assert examiner_assignments.status_code == 403

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
    exam_data["total_marks"] = 4
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
        update_data["total_marks"] = 4
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
    fourth_update["total_marks"] = 4
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
    exam_data["total_marks"] = 4
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
    update_data["total_marks"] = 4
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


def test_copying_questions_from_multiple_creators_uses_destination_exam_marks(client, db_session):
    exam_creator = create_user(db_session, "examiner", "destination_exam_creator@test.com")
    first_owner = create_user(db_session, "examiner", "first_source_owner@test.com")
    second_owner = create_user(db_session, "admin", "second_source_owner@test.com")

    exam = Exam(
        title="Destination Marks Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=2,
        created_by=exam_creator.id,
    )
    first_bank = QuestionCollection(name="First Owner Bank", created_by=first_owner.id)
    second_bank = QuestionCollection(name="Second Owner Bank", created_by=second_owner.id)
    db_session.add_all([exam, first_bank, second_bank])
    db_session.flush()

    first_question = QuestionBank(
        question_text="Question from first creator",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        expected_answer="First expected answer",
        model_answer_text="First model answer",
        marks=2,
        negative_marks=0.75,
        question_image_data=b"first-prompt-image",
        question_image_mime_type="image/png",
        expected_answer_image_data=b"first-answer-image",
        expected_answer_image_mime_type="image/png",
        created_by=first_owner.id,
    )
    second_question = QuestionBank(
        question_text="Question from second creator",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        expected_answer="Second expected answer",
        marks=8,
        negative_marks=1.25,
        created_by=second_owner.id,
    )
    db_session.add_all([first_question, second_question])
    db_session.flush()
    db_session.add_all([
        Option(question_id=first_question.id, option_text="Correct choice", is_correct=True),
        Option(question_id=first_question.id, option_text="Wrong choice", is_correct=False),
        Option(question_id=second_question.id, option_text="Correct choice 2", is_correct=True),
        QuestionCollectionItem(collection_id=first_bank.id, question_id=first_question.id),
        QuestionCollectionItem(collection_id=second_bank.id, question_id=second_question.id),
    ])
    db_session.commit()

    response = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [first_question.id, second_question.id]},
        headers=get_auth_headers(exam_creator),
    )
    assert response.status_code == 201

    copied_rows = db_session.query(ExamQuestion, QuestionBank).join(
        QuestionBank, QuestionBank.id == ExamQuestion.question_id
    ).filter(ExamQuestion.exam_id == exam.id).order_by(ExamQuestion.question_order).all()
    assert len(copied_rows) == 2
    copied_by_text = {question.question_text: question for _, question in copied_rows}

    first_copy = copied_by_text["Question from first creator"]
    second_copy = copied_by_text["Question from second creator"]
    assert first_copy.marks == 1
    assert second_copy.marks == 1
    assert first_copy.negative_marks == 0
    assert second_copy.negative_marks == 0
    assert copied_rows[0][0].question_time_limit_seconds is None
    assert copied_rows[1][0].question_time_limit_seconds is None
    assert first_question.negative_marks == 0.75
    assert second_question.negative_marks == 1.25
    assert first_question.marks == 2
    assert second_question.marks == 8
    assert first_copy.expected_answer == "First expected answer"
    assert first_copy.model_answer_text == "First model answer"
    assert first_copy.question_image_data == b"first-prompt-image"
    assert first_copy.expected_answer_image_data == b"first-answer-image"
    copied_options = db_session.query(Option).filter(Option.question_id == first_copy.id).all()
    assert {(option.option_text, option.is_correct) for option in copied_options} == {
        ("Correct choice", True),
        ("Wrong choice", False),
    }

    marks_response = client.put(
        f"/exams/{exam.id}/question-marks",
        json={"marks_by_group": {"easy|MCQ": 6}},
        headers=get_auth_headers(exam_creator),
    )
    assert marks_response.status_code == 200
    db_session.refresh(first_copy)
    db_session.refresh(second_copy)
    assert first_copy.marks == 6
    assert second_copy.marks == 6
    assert first_question.marks == 2
    assert second_question.marks == 8


def test_reusing_previous_exam_questions_keeps_destination_exam_marks_independent(client, db_session):
    creator = create_user(db_session, "examiner", "reuse_marks_creator@test.com")
    source_exam = Exam(
        title="Source Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(source_exam)
    db_session.flush()
    source_question = QuestionBank(
        question_text="Reusable source question",
        question_type="short_answer",
        subject="Science",
        difficulty="medium",
        expected_answer="Source answer",
        marks=9,
        created_by=creator.id,
    )
    db_session.add(source_question)
    db_session.flush()
    db_session.add(ExamQuestion(
        exam_id=source_exam.id,
        question_id=source_question.id,
        question_order=1,
    ))
    target_exam = Exam(
        title="New Destination Exam",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=creator.id,
    )
    db_session.add(target_exam)
    db_session.commit()

    response = client.post(
        f"/exams/{target_exam.id}/question-bank/reuse",
        json={"question_ids": [source_question.id]},
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 201
    copied_id = db_session.query(ExamQuestion.question_id).filter(
        ExamQuestion.exam_id == target_exam.id
    ).scalar()
    copied = db_session.get(QuestionBank, copied_id)
    assert copied.question_text == source_question.question_text
    assert copied.expected_answer == "Source answer"
    assert copied.marks == 1
    assert source_question.marks == 9

    marks_response = client.put(
        f"/exams/{target_exam.id}/question-marks",
        json={"marks_by_group": {"medium|short_answer": 4}},
        headers=get_auth_headers(creator),
    )
    assert marks_response.status_code == 200
    db_session.refresh(copied)
    assert copied.marks == 4
    assert source_question.marks == 9


def test_question_pool_can_contain_more_questions_than_each_student_paper(client, db_session):
    exam_creator = create_user(db_session, "examiner", "flexible_pool_creator@test.com")
    source_owner = create_user(db_session, "examiner", "flexible_pool_source@test.com")
    exam = Exam(
        title="Flexible Question Pool",
        subject="Science",
        duration_minutes=30,
        total_questions=2,
        selection_rules={"group_counts": {"easy|MCQ": 2}},
        created_by=exam_creator.id,
    )
    bank = QuestionCollection(name="Large Science Pool", created_by=source_owner.id)
    db_session.add_all([exam, bank])
    db_session.flush()
    source_questions = [
        QuestionBank(
            question_text=f"Pool question {index}",
            question_type="MCQ",
            subject="Science",
            difficulty="easy",
            marks=1,
            negative_marks=0,
            created_by=source_owner.id,
        )
        for index in range(3)
    ]
    db_session.add_all(source_questions)
    db_session.flush()
    for question in source_questions:
        db_session.add(QuestionCollectionItem(
            collection_id=bank.id,
            question_id=question.id,
        ))
    db_session.commit()

    response = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [question.id for question in source_questions]},
        headers=get_auth_headers(exam_creator),
    )
    assert response.status_code == 201
    assert response.json()["question_count"] == 3
    assert db_session.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id
    ).count() == 3


def test_question_pool_can_be_left_empty_during_exam_setup(client, db_session):
    creator = create_user(db_session, "examiner", "empty_pool_creator@test.com")
    exam = Exam(
        title="Build Questions Later",
        subject="Science",
        duration_minutes=30,
        total_questions=2,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.commit()

    response = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": []},
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 201
    assert response.json()["question_count"] == 0


def test_exam_creator_can_set_negative_marks_for_each_exam_question(client, db_session):
    creator = create_user(db_session, "examiner", "question_penalty_creator@test.com")
    exam = Exam(
        title="Per Question Penalties",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        negative_marking=True,
        created_by=creator.id,
    )
    question = QuestionBank(
        question_text="Penalty test question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=2,
        negative_marks=0,
        created_by=creator.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=question.id, question_order=1))
    db_session.commit()

    response = client.patch(
        f"/exams/{exam.id}/questions/{question.id}/negative-marks",
        json={"negative_marks": 0.75},
        headers=get_auth_headers(creator),
    )
    assert response.status_code == 200
    assert response.json()["negative_marks"] == 0.75
    db_session.refresh(question)
    assert question.negative_marks == 0.75



def test_adding_questions_from_another_bank_preserves_existing_exam_pool(client, db_session):
    creator = create_user(db_session, "examiner", "append_bank_creator@test.com")
    bank_owner = create_user(db_session, "examiner", "append_bank_owner@test.com")
    exam = Exam(
        title="Edit Existing Examination",
        subject="Science",
        duration_minutes=30,
        total_questions=2,
        created_by=creator.id,
    )
    existing_question = QuestionBank(
        question_text="Question already in the exam",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    first_bank = QuestionCollection(name="First source bank", created_by=bank_owner.id)
    second_bank = QuestionCollection(name="Second source bank", created_by=bank_owner.id)
    db_session.add_all([exam, existing_question, first_bank, second_bank])
    db_session.flush()
    db_session.add(ExamQuestion(exam_id=exam.id, question_id=existing_question.id, question_order=1))
    first_source = QuestionBank(
        question_text="Question from first bank",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=5,
        created_by=bank_owner.id,
    )
    second_source = QuestionBank(
        question_text="Question from second bank",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=8,
        created_by=bank_owner.id,
    )
    db_session.add_all([first_source, second_source])
    db_session.flush()
    db_session.add_all([
        QuestionCollectionItem(collection_id=first_bank.id, question_id=first_source.id),
        QuestionCollectionItem(collection_id=second_bank.id, question_id=second_source.id),
    ])
    db_session.commit()

    first_response = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [first_source.id]},
        headers=get_auth_headers(creator),
    )
    assert first_response.status_code == 201
    assert first_response.json()["total_question_count"] == 2

    second_response = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [second_source.id]},
        headers=get_auth_headers(creator),
    )
    assert second_response.status_code == 201
    assert second_response.json()["question_count"] == 1
    assert second_response.json()["total_question_count"] == 3

    copied_rows = db_session.query(ExamQuestion, QuestionBank).join(
        QuestionBank, QuestionBank.id == ExamQuestion.question_id
    ).filter(ExamQuestion.exam_id == exam.id).order_by(ExamQuestion.question_order).all()
    assert [question.question_text for _, question in copied_rows] == [
        "Question already in the exam",
        "Question from first bank",
        "Question from second bank",
    ]
    assert copied_rows[1][1].source_question_id == first_source.id
    assert copied_rows[2][1].source_question_id == second_source.id

    duplicate_response = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [second_source.id]},
        headers=get_auth_headers(creator),
    )
    assert duplicate_response.status_code == 201
    assert duplicate_response.json()["question_count"] == 0
    assert db_session.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).count() == 3


def test_imported_questions_must_match_exam_configured_type_and_difficulty(client, db_session):
    creator = create_user(db_session, "examiner", "eligible_import_creator@test.com")
    bank_owner = create_user(db_session, "examiner", "eligible_import_bank_owner@test.com")
    exam = Exam(
        title="Configured Question Levels",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        selection_rules={"group_counts": {"easy|MCQ": 1}},
        created_by=creator.id,
    )
    bank = QuestionCollection(name="Mixed Levels", created_by=bank_owner.id)
    db_session.add_all([exam, bank])
    db_session.flush()

    eligible_questions = [
        QuestionBank(
            question_text=f"Eligible easy MCQ {index}",
            question_type="MCQ",
            subject="Science",
            difficulty="easy",
            marks=5 + index,
            negative_marks=0.5,
            created_by=bank_owner.id,
        )
        for index in range(2)
    ]
    ineligible_question = QuestionBank(
        question_text="Ineligible medium MCQ",
        question_type="MCQ",
        subject="Science",
        difficulty="medium",
        marks=9,
        created_by=bank_owner.id,
    )
    db_session.add_all(eligible_questions + [ineligible_question])
    db_session.flush()
    for question in eligible_questions + [ineligible_question]:
        db_session.add(QuestionCollectionItem(collection_id=bank.id, question_id=question.id))
    db_session.commit()

    rejected = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [eligible_questions[0].id, ineligible_question.id]},
        headers=get_auth_headers(creator),
    )
    assert rejected.status_code == 400
    assert "configured for this examination" in rejected.json()["detail"]["message"]
    assert db_session.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).count() == 0

    accepted = client.post(
        f"/question-banks/select-for-exam/{exam.id}",
        json={"question_ids": [question.id for question in eligible_questions]},
        headers=get_auth_headers(creator),
    )
    assert accepted.status_code == 201
    assert accepted.json()["question_count"] == 2
    copied_questions = db_session.query(QuestionBank).join(
        ExamQuestion, ExamQuestion.question_id == QuestionBank.id
    ).filter(ExamQuestion.exam_id == exam.id).all()
    assert len(copied_questions) == 2
    assert all(question.difficulty == "easy" and question.question_type == "MCQ" for question in copied_questions)
    assert all(question.marks == 1 for question in copied_questions)
    assert all(question.negative_marks == 0 for question in copied_questions)



def test_admin_cannot_delete_examination_created_by_another_user(client, db_session):
    owner = create_user(db_session, "examiner", "exam_owner_for_admin_delete@test.com")
    admin = create_user(db_session, "admin", "exam_admin_delete@test.com")

    created = client.post(
        "/exams/",
        json=valid_exam_data(),
        headers=get_auth_headers(owner),
    )
    assert created.status_code == 201
    exam_id = created.json()["exam_id"]

    deleted = client.delete(
        f"/exams/{exam_id}",
        headers=get_auth_headers(admin),
    )

    assert deleted.status_code == 403
    assert db_session.query(Exam).filter(Exam.id == exam_id).first() is not None

def test_exam_creator_cannot_assign_students_after_schedule_end(client, db_session):
    creator = create_user(
        db_session,
        "admin",
        "assignment_deadline_creator@test.com",
    )
    student = create_user(
        db_session,
        "student",
        "assignment_deadline_student@test.com",
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam = Exam(
        title="Ended Examination",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=now - timedelta(hours=2),
        end_time=now - timedelta(minutes=1),
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    response = client.post(
        f"/exams/{exam.id}/assignments",
        json={"student_ids": [student.id]},
        headers=get_auth_headers(creator),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Exam has ended. New students cannot be assigned."
    assignment = db_session.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam.id,
        ExamAssignment.student_id == student.id,
    ).first()
    assert assignment is None




def test_examiner_can_reuse_questions_from_another_exam_creator(client, db_session):
    source_owner = create_user(db_session, "admin", "cross_creator_source@test.com")
    exam_creator = create_user(db_session, "examiner", "cross_creator_target@test.com")
    source_exam = Exam(
        title="Admin Source Examination",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=source_owner.id,
    )
    db_session.add(source_exam)
    db_session.flush()
    source_question = QuestionBank(
        question_text="Question from another creator",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=2,
        created_by=source_owner.id,
    )
    target_exam = Exam(
        title="Examiner Destination Examination",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        created_by=exam_creator.id,
    )
    db_session.add_all([source_question, target_exam])
    db_session.flush()
    db_session.add(ExamQuestion(
        exam_id=source_exam.id,
        question_id=source_question.id,
        question_order=1,
    ))
    db_session.commit()

    sources = client.get(
        f"/exams/{target_exam.id}/question-bank/sources",
        headers=get_auth_headers(exam_creator),
    )
    assert sources.status_code == 200
    assert any(
        bank["source_exam_id"] == source_exam.id
        for bank in sources.json()["banks"]
    )

    copied = client.post(
        f"/exams/{target_exam.id}/question-bank/reuse",
        json={"question_ids": [source_question.id]},
        headers=get_auth_headers(exam_creator),
    )
    assert copied.status_code == 201
    copied_question_id = copied.json()["copied_question_ids"][0]
    copied_question = db_session.query(QuestionBank).filter(
        QuestionBank.id == copied_question_id
    ).first()
    assert copied_question is not None
    assert copied_question.source_question_id == source_question.id
    assert copied_question.created_by == exam_creator.id


def test_exam_question_bank_cannot_be_changed_after_scheduled_start(client, db_session):
    creator = create_user(db_session, "examiner", "started_bank_creator@test.com")
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam = Exam(
        title="Started Examination",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=now - timedelta(minutes=1),
        end_time=now + timedelta(hours=1),
        created_by=creator.id,
    )
    question = QuestionBank(
        question_text="Existing question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=1,
        created_by=creator.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add(ExamQuestion(
        exam_id=exam.id,
        question_id=question.id,
        question_order=1,
    ))
    db_session.commit()

    removed = client.delete(
        f"/exams/{exam.id}/questions/{question.id}",
        headers=get_auth_headers(creator),
    )
    assert removed.status_code == 409
    assert removed.json()["detail"] == (
        "The examination has started. Its question bank can no longer be changed."
    )
    assert db_session.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam.id,
        ExamQuestion.question_id == question.id,
    ).first() is not None


def test_exam_creator_can_publish_and_publication_time_is_returned(client, db_session):
    creator = create_user(db_session, "examiner", "publish_exam_creator@test.com")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    exam = Exam(
        title="Ready to Publish",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=start.replace(tzinfo=None),
        end_time=(start + timedelta(hours=1)).replace(tzinfo=None),
        created_by=creator.id,
    )
    question = QuestionBank(
        question_text="Published exam question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=5,
        created_by=creator.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add(ExamQuestion(
        exam_id=exam.id,
        question_id=question.id,
        question_order=1,
    ))
    db_session.commit()

    response = client.post(
        f"/exams/{exam.id}/publish",
        headers=get_auth_headers(creator),
    )

    assert response.status_code == 200
    assert response.json()["message"] == "Examination published successfully."
    assert response.json()["published_at"]

    listing = client.get("/exams/", headers=get_auth_headers(creator))
    listed_exam = next(item for item in listing.json() if item["id"] == exam.id)
    assert listed_exam["published_at"] == response.json()["published_at"]


def test_exam_cannot_be_published_without_schedule_or_enough_questions(client, db_session):
    creator = create_user(db_session, "examiner", "publish_exam_incomplete@test.com")
    exam = Exam(
        title="Incomplete Examination",
        subject="Science",
        duration_minutes=30,
        total_questions=2,
        created_by=creator.id,
    )
    db_session.add(exam)
    db_session.commit()

    response = client.post(
        f"/exams/{exam.id}/publish",
        headers=get_auth_headers(creator),
    )

    assert response.status_code == 409
    assert response.json()["detail"] == (
        "Set the examination start and end times before publishing."
    )


def test_only_exam_creator_can_publish_an_examination(client, db_session):
    owner = create_user(db_session, "examiner", "publish_exam_owner@test.com")
    other_creator = create_user(db_session, "admin", "publish_exam_other@test.com")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    exam = Exam(
        title="Owned Examination",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=start.replace(tzinfo=None),
        end_time=(start + timedelta(hours=1)).replace(tzinfo=None),
        created_by=owner.id,
    )
    db_session.add(exam)
    db_session.commit()

    response = client.post(
        f"/exams/{exam.id}/publish",
        headers=get_auth_headers(other_creator),
    )

    assert response.status_code == 403
    assert response.json()["detail"] == (
        "Only the examination creator can publish this exam."
    )


def test_publishing_an_exam_twice_keeps_the_original_publication_time(client, db_session):
    creator = create_user(db_session, "admin", "publish_exam_idempotent@test.com")
    start = datetime.now(timezone.utc) + timedelta(days=1)
    exam = Exam(
        title="Idempotent Publication",
        subject="Science",
        duration_minutes=30,
        total_questions=1,
        start_time=start.replace(tzinfo=None),
        end_time=(start + timedelta(hours=1)).replace(tzinfo=None),
        created_by=creator.id,
    )
    question = QuestionBank(
        question_text="One required question",
        question_type="MCQ",
        subject="Science",
        difficulty="easy",
        marks=5,
        created_by=creator.id,
    )
    db_session.add_all([exam, question])
    db_session.flush()
    db_session.add(ExamQuestion(
        exam_id=exam.id,
        question_id=question.id,
        question_order=1,
    ))
    db_session.commit()

    first = client.post(f"/exams/{exam.id}/publish", headers=get_auth_headers(creator))
    second = client.post(f"/exams/{exam.id}/publish", headers=get_auth_headers(creator))

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["published_at"] == first.json()["published_at"]



def test_unconfigured_random_papers_are_frozen_when_students_are_assigned(client, db_session):
    creator = create_user(db_session, "examiner", "fixed-paper-creator@test.com")
    first_student = create_user(db_session, "student", "fixed-paper-one@test.com")
    second_student = create_user(db_session, "student", "fixed-paper-two@test.com")

    start = datetime.now(timezone.utc) + timedelta(hours=1)
    exam_data = {
        "title": "Fixed Random Papers",
        "subject": "General Knowledge",
        "duration_minutes": 30,
        "total_questions": 1,
        "total_marks": 2,
        "randomize_questions": True,
        "selection_rules": {},
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=2)).isoformat(),
    }
    create_response = client.post(
        "/exams/",
        json=exam_data,
        headers=get_auth_headers(creator),
    )
    assert create_response.status_code == 201
    exam_id = create_response.json()["exam_id"]
    exam = db_session.query(Exam).filter(Exam.id == exam_id).first()

    questions = [
        QuestionBank(
            question_text=f"Fixed paper question {index}",
            question_type="MCQ",
            subject="General Knowledge",
            difficulty="easy",
            marks=2,
        )
        for index in range(3)
    ]
    db_session.add_all(questions)
    db_session.commit()
    for order, question in enumerate(questions, start=1):
        db_session.add(ExamQuestion(
            exam_id=exam.id,
            question_id=question.id,
            question_order=order,
        ))
    db_session.commit()

    assign_response = client.post(
        f"/exams/{exam_id}/assignments",
        json={"student_ids": [first_student.id, second_student.id]},
        headers=get_auth_headers(creator),
    )
    assert assign_response.status_code == 200

    sessions = db_session.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id.in_([first_student.id, second_student.id]),
    ).all()
    assert len(sessions) == 2
    assert all(session.status == "not_started" for session in sessions)
    assert all(session.started_at is None for session in sessions)
    assert all(len(session.selected_question_ids) == 1 for session in sessions)

    question_marks = {question.id: question.marks for question in questions}
    assert all(
        sum(question_marks[question_id] for question_id in session.selected_question_ids) == 2
        for session in sessions
    )
    assert set(sessions[0].selected_question_ids) != set(sessions[1].selected_question_ids)

    first_paper = list(sessions[0].selected_question_ids)
    revoke_response = client.delete(
        f"/exams/{exam_id}/assignments/{first_student.id}",
        headers=get_auth_headers(creator),
    )
    assert revoke_response.status_code == 200

    reassign_response = client.post(
        f"/exams/{exam_id}/assignments",
        json={"student_ids": [first_student.id]},
        headers=get_auth_headers(creator),
    )
    assert reassign_response.status_code == 200
    db_session.refresh(sessions[0])
    assert sessions[0].selected_question_ids == first_paper
