from datetime import datetime, timedelta

from app.auth import hash_password
from app.models import (
    Answer,
    Exam,
    ExamAssignment,
    ExamQuestion,
    ExamSession,
    QuestionBank,
    Result,
    User,
)


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
    distribution = data["cohort_distribution"]
    assert distribution["cohort_size"] == 1
    assert distribution["current_student_percentage"] == 75.0
    assert sum(band["count"] for band in distribution["score_bands"]) == 1
    assert distribution["score_bands"][7]["count"] == 1
    assert all("email" not in band for band in distribution["score_bands"])


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


def test_student_can_view_only_their_published_result_face_photo(client, db_session):
    student = create_user(db_session, "result-photo-owner@example.com")
    other_student = create_user(db_session, "result-photo-other@example.com")
    exam = Exam(title="Face Photo Result", duration_minutes=30, total_questions=1)
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)
    session, _ = create_published_result(db_session, student, exam, published=True)
    session.face_capture_data = b"private-face-photo-bytes"
    session.face_capture_mime_type = "image/jpeg"
    db_session.commit()

    photo = client.get(
        f"/results/sessions/{session.id}/face-photo",
        headers=login_headers(client, student.email),
    )
    assert photo.status_code == 200
    assert photo.content == b"private-face-photo-bytes"
    assert photo.headers.get("cache-control") == "private, no-store"

    denied = client.get(
        f"/results/sessions/{session.id}/face-photo",
        headers=login_headers(client, other_student.email),
    )
    assert denied.status_code == 403


def test_student_cannot_view_face_photo_before_result_publication(client, db_session):
    student = create_user(db_session, "result-photo-unpublished@example.com")
    exam = Exam(title="Unpublished Face Photo", duration_minutes=30, total_questions=1)
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)
    session, _ = create_published_result(db_session, student, exam, published=False)
    session.face_capture_data = b"private-face-photo-bytes"
    session.face_capture_mime_type = "image/jpeg"
    db_session.commit()

    response = client.get(
        f"/results/sessions/{session.id}/face-photo",
        headers=login_headers(client, student.email),
    )
    assert response.status_code == 404



def _create_ended_assigned_paper(db_session, student, creator):
    now = datetime.utcnow()
    exam = Exam(
        title="Assigned Paper Report",
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

    questions = [
        QuestionBank(
            question_text=f"Report question {index}",
            question_type="short_answer",
            subject="Science",
            difficulty="easy",
            marks=2,
            expected_answer=f"Expected answer {index}",
        )
        for index in range(2)
    ]
    db_session.add_all(questions)
    db_session.commit()
    for order, question in enumerate(questions, start=1):
        db_session.add(ExamQuestion(
            exam_id=exam.id,
            question_id=question.id,
            question_order=order,
        ))
    db_session.add(ExamAssignment(
        exam_id=exam.id,
        student_id=student.id,
        assigned_by=creator.id,
        is_active=True,
    ))
    db_session.commit()
    return exam, questions


def test_unattempted_student_sees_only_their_fixed_paper_without_fabricated_answers(
    client, db_session
):
    student = create_user(db_session, "unattempted-paper@example.com")
    creator = create_user(db_session, "unattempted-paper-creator@example.com", role="examiner")
    exam, questions = _create_ended_assigned_paper(db_session, student, creator)
    assigned_question = questions[1]
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=None,
        submitted_at=None,
        status="not_started",
        selected_question_ids=[assigned_question.id],
    )
    db_session.add(session)
    db_session.commit()

    response = client.get(
        f"/results/exams/{exam.id}/paper",
        headers=login_headers(client, student.email),
    )

    assert response.status_code == 200
    paper = response.json()["paper"]
    assert len(paper) == 1
    assert paper[0]["question_id"] == assigned_question.id
    assert paper[0]["correct_answer"] == assigned_question.expected_answer
    assert paper[0]["student_answer"] is None
    assert paper[0]["awarded_marks"] is None
    assert paper[0]["maximum_marks"] == 2


def test_attempted_student_cannot_view_answers_until_result_is_published(
    client, db_session
):
    student = create_user(db_session, "attempted-paper@example.com")
    creator = create_user(db_session, "attempted-paper-creator@example.com", role="examiner")
    exam, questions = _create_ended_assigned_paper(db_session, student, creator)
    assigned_question = questions[0]
    now = datetime.utcnow()
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now - timedelta(minutes=30),
        submitted_at=now - timedelta(minutes=1),
        status="submitted",
        selected_question_ids=[assigned_question.id],
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)
    db_session.add(Answer(
        session_id=session.id,
        question_id=assigned_question.id,
        answer_text="Student's submitted answer",
        awarded_marks=1.5,
    ))
    result = Result(
        session_id=session.id,
        total_marks=2,
        obtained_marks=1.5,
        percentage=75,
        question_scores=[],
        evaluated_at=now,
        is_published=False,
    )
    db_session.add(result)
    db_session.commit()

    headers = login_headers(client, student.email)
    blocked = client.get(
        f"/results/exams/{exam.id}/paper",
        headers=headers,
    )
    assert blocked.status_code == 403

    result.is_published = True
    result.published_at = datetime.utcnow()
    db_session.commit()
    published = client.get(
        f"/results/exams/{exam.id}/paper",
        headers=headers,
    )
    assert published.status_code == 200
    paper = published.json()["paper"]
    assert len(paper) == 1
    assert paper[0]["question_id"] == assigned_question.id
    assert paper[0]["student_answer"] == "Student's submitted answer"
    assert paper[0]["awarded_marks"] == 1.5
    assert paper[0]["maximum_marks"] == 2
    assert paper[0]["correct_answer"] == assigned_question.expected_answer



def test_admin_performance_report_uses_exact_students_assigned_paper(client, db_session):
    student = create_user(db_session, "admin-report-student@example.com")
    creator = create_user(db_session, "admin-report-creator@example.com", role="examiner")
    admin = create_user(db_session, "admin-report-admin@example.com", role="admin")
    exam, questions = _create_ended_assigned_paper(db_session, student, creator)
    assigned_question = questions[1]
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=None,
        submitted_at=None,
        status="not_started",
        selected_question_ids=[assigned_question.id],
    )
    db_session.add(session)
    db_session.commit()

    response = client.get(
        f"/results/exams/{exam.id}/students/{student.id}/paper",
        headers=login_headers(client, admin.email),
    )

    assert response.status_code == 200
    report = response.json()
    assert report["paper_is_preview"] is False
    assert len(report["paper"]) == 1
    assert report["paper"][0]["question_id"] == assigned_question.id
    assert report["paper"][0]["correct_answer"] == assigned_question.expected_answer
    assert report["paper"][0]["student_answer"] is None
    assert report["paper"][0]["awarded_marks"] is None
