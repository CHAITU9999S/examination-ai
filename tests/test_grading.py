import io
from datetime import datetime, timedelta, timezone

from PIL import Image

import pytest

from app.auth import create_access_token
from app.models import Answer, Exam, ExamSession, Option, QuestionBank, Result, User


@pytest.fixture
def grading_data(db_session):
    examiner = User(
        full_name="Grading Examiner",
        email="grading-examiner@example.com",
        password_hash="test-password-hash",
        role="examiner",
        is_active=True,
    )
    student = User(
        full_name="Grading Student",
        email="grading-student@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )
    db_session.add_all([examiner, student])
    db_session.commit()
    db_session.refresh(examiner)
    db_session.refresh(student)

    exam = Exam(
        title="Subjective Grading Test",
        subject="Computer Science",
        duration_minutes=30,
        total_questions=1,
        negative_marking=False,
        proctoring_enabled=False,
        created_by=examiner.id,
    )
    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    question = QuestionBank(
        question_text="Explain a database.",
        question_type="short_answer",
        subject="Computer Science",
        difficulty="easy",
        marks=5,
        negative_marks=0,
        expected_answer="A database is an organized collection of data.",
        model_answer_text="A database stores and organizes related information.",
    )
    db_session.add(question)
    db_session.commit()
    db_session.refresh(question)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now - timedelta(minutes=20),
        submitted_at=now,
        expires_at=now - timedelta(minutes=1),
        status="submitted",
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    answer = Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text="A database stores organized information.",
    )
    db_session.add(answer)
    db_session.commit()
    db_session.refresh(answer)

    return {
        "examiner": examiner,
        "student": student,
        "exam": exam,
        "question": question,
        "session": session,
        "answer": answer,
    }


def auth_headers(user):
    token = create_access_token(str(user.id))
    return {"Authorization": f"Bearer {token}"}


def test_examiner_can_manually_grade_subjective_answer(
    client,
    db_session,
    grading_data,
):
    data = grading_data

    response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={"awarded_marks": 4.0},
    )

    assert response.status_code == 200
    assert response.json()["awarded_marks"] == pytest.approx(4.0)
    assert response.json()["result_ready"] is True

    saved_answer = db_session.query(Answer).filter(
        Answer.id == data["answer"].id,
    ).first()
    saved_result = db_session.query(Result).filter(
        Result.session_id == data["session"].id,
    ).first()

    assert saved_answer.awarded_marks == pytest.approx(4.0)
    assert saved_result.total_marks == pytest.approx(5.0)
    assert saved_result.obtained_marks == pytest.approx(4.0)
    assert saved_result.percentage == pytest.approx(80.0)


def test_admin_cannot_grade_an_exam_created_by_an_examiner(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    admin = User(
        full_name="Test Admin",
        email="grading-admin@example.com",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(admin),
        json={"awarded_marks": 4.0},
    )

    assert response.status_code == 403
    db_session.refresh(data["answer"])
    assert data["answer"].awarded_marks is None


def test_admin_can_view_an_examiner_exam_without_changing_marks(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    admin = User(
        full_name="Read Only Admin",
        email="grading-readonly-admin@example.com",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    response = client.get(
        f"/grading/exams/{data['exam'].id}/pending",
        headers=auth_headers(admin),
    )

    assert response.status_code == 200
    assert response.json()["exam_id"] == data["exam"].id


def test_previously_graded_answers_can_be_loaded(
    client,
    grading_data,
):
    data = grading_data
    grade_response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={"awarded_marks": 4.0},
    )
    assert grade_response.status_code == 200

    response = client.get(
        "/grading/graded",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 200
    assert response.json()["total_graded"] == 1
    assert response.json()["answers"][0]["answer_id"] == data["answer"].id


def test_invalid_ai_approval_rubric_does_not_save_marks(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    response = client.post(
        f"/grading/answers/{data['answer'].id}/approve-ai",
        headers=auth_headers(data["examiner"]),
        json={
            "awarded_marks": 4.0,
            "rubric_scores": [
                {
                    "criterion": "Correctness",
                    "max_marks": 2.0,
                    "awarded_marks": 2.0,
                }
            ],
        },
    )

    assert response.status_code == 400
    db_session.rollback()
    saved_answer = db_session.query(Answer).filter(
        Answer.id == data["answer"].id,
    ).first()
    assert saved_answer.awarded_marks is None

def test_ai_grading_is_disabled_without_explicit_opt_in(
    client,
    grading_data,
    monkeypatch,
):
    data = grading_data

    monkeypatch.setenv("AI_GRADING_ENABLED", "false")
    monkeypatch.setenv("MENTORS_API_KEY", "test-key-not-used")

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


def test_student_cannot_manually_grade_subjective_answer(
    client,
    grading_data,
):
    data = grading_data

    response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["student"]),
        json={"awarded_marks": 4.0},
    )

    assert response.status_code == 403

def test_examiner_can_load_pending_grading_queue(
    client,
    grading_data,
):
    data = grading_data
    response = client.get(
        "/grading/pending",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["total_pending"] == 1
    pending = payload["answers"][0]
    assert pending["answer_id"] == data["answer"].id
    assert pending["exam_id"] == data["exam"].id
    assert pending["marks"] == pytest.approx(5.0)
    assert pending["answer_text"] == data["answer"].answer_text

def test_examiner_can_view_uploaded_answer_image(
    client,
    db_session,
    grading_data,
    monkeypatch,
    tmp_path,
):
    data = grading_data
    upload_root = tmp_path / "uploads"
    answer_directory = upload_root / "answers"
    answer_directory.mkdir(parents=True)
    image_path = answer_directory / "grading-answer.png"

    image_buffer = io.BytesIO()
    Image.new("RGB", (16, 16), color="white").save(image_buffer, format="PNG")
    expected_bytes = image_buffer.getvalue()
    image_path.write_bytes(expected_bytes)

    data["answer"].image_path = "answers/grading-answer.png"
    db_session.commit()
    monkeypatch.setenv("UPLOAD_DIRECTORY", str(upload_root))

    response = client.get(
        f"/grading/answers/{data['answer'].id}/image",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content == expected_bytes


def test_student_cannot_view_uploaded_answer_image(
    client,
    grading_data,
):
    data = grading_data
    data["answer"].image_path = "answers/private.png"

    response = client.get(
        f"/grading/answers/{data['answer'].id}/image",
        headers=auth_headers(data["student"]),
    )

    assert response.status_code == 403




def _mock_openai_response(monkeypatch, payload):
    import json
    from types import SimpleNamespace

    class FakeCompletions:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[
                    SimpleNamespace(
                        message=SimpleNamespace(content=json.dumps(payload))
                    )
                ]
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(
                completions=FakeCompletions()
            )

    monkeypatch.setattr(
        "app.services.subjective_grading.OpenAI",
        FakeOpenAI,
    )


def test_ai_grading_generates_and_persists_suggestion_without_awarding_marks(
    client,
    db_session,
    grading_data,
    monkeypatch,
):
    data = grading_data
    monkeypatch.setenv("AI_GRADING_ENABLED", "true")
    monkeypatch.setenv("MENTORS_API_KEY", "test-key")
    monkeypatch.setenv("AI_GRADING_MODEL", "test-model")
    _mock_openai_response(
        monkeypatch,
        {
            "suggested_marks": 4.5,
            "justification": "The answer correctly explains organized data.",
            "matched_points": ["Explains organized information."],
            "missed_points": ["Does not mention relationships between records."],
        },
    )

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["suggested_marks"] == pytest.approx(4.5)
    assert payload["maximum_marks"] == pytest.approx(5.0)
    assert payload["status"] == "pending_examiner_approval"

    db_session.refresh(data["answer"])
    assert data["answer"].ai_suggested_marks == pytest.approx(4.5)
    assert data["answer"].ai_model == "test-model"
    assert data["answer"].awarded_marks is None


def test_ai_grading_rejects_score_above_question_maximum(
    client,
    db_session,
    grading_data,
    monkeypatch,
):
    data = grading_data
    monkeypatch.setenv("AI_GRADING_ENABLED", "true")
    monkeypatch.setenv("MENTORS_API_KEY", "test-key")
    _mock_openai_response(
        monkeypatch,
        {
            "suggested_marks": 9,
            "justification": "Invalid score.",
            "matched_points": [],
            "missed_points": [],
        },
    )

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 502
    db_session.refresh(data["answer"])
    assert data["answer"].ai_suggested_marks is None
    assert data["answer"].awarded_marks is None


def test_examiner_can_approve_ai_suggestion_as_final_marks(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    data["answer"].ai_suggested_marks = 4.0
    data["answer"].ai_justification = "Mostly correct."
    db_session.commit()

    response = client.post(
        f"/grading/answers/{data['answer'].id}/approve-ai",
        headers=auth_headers(data["examiner"]),
        json={"awarded_marks": 3.5},
    )

    assert response.status_code == 200
    assert response.json()["awarded_marks"] == pytest.approx(3.5)

    db_session.refresh(data["answer"])
    assert data["answer"].awarded_marks == pytest.approx(3.5)


def test_student_cannot_request_ai_grading(
    client,
    grading_data,
    monkeypatch,
):
    data = grading_data
    monkeypatch.setenv("AI_GRADING_ENABLED", "true")
    monkeypatch.setenv("MENTORS_API_KEY", "test-key")

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["student"]),
    )

    assert response.status_code == 403


def test_ai_grading_requires_uploaded_image_for_image_upload_answers(
    client,
    db_session,
    grading_data,
    monkeypatch,
):
    data = grading_data
    data["question"].question_type = "image_upload"
    db_session.commit()
    monkeypatch.setenv("AI_GRADING_ENABLED", "true")
    monkeypatch.setenv("MENTORS_API_KEY", "test-key")

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 400
    assert "no uploaded answer image" in response.json()["detail"].lower()


def test_examiner_review_queue_groups_answers_by_question(
    client,
    grading_data,
):
    data = grading_data
    response = client.get(
        f"/grading/exams/{data['exam'].id}/review-groups",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 200
    groups = response.json()["question_groups"]
    assert len(groups) == 1
    assert groups[0]["question_id"] == data["question"].id
    assert groups[0]["answers"][0]["answer_id"] == data["answer"].id


def test_examiner_can_bulk_grade_and_save_feedback(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    response = client.post(
        f"/grading/sessions/{data['session'].id}/bulk-grade",
        headers=auth_headers(data["examiner"]),
        json={
            "grades": [
                {
                    "answer_id": data["answer"].id,
                    "awarded_marks": 4.0,
                    "examiner_feedback": "Good explanation.",
                }
            ]
        },
    )

    assert response.status_code == 200
    assert response.json()["graded_answer_count"] == 1
    db_session.refresh(data["answer"])
    assert data["answer"].awarded_marks == pytest.approx(4.0)
    assert data["answer"].examiner_feedback == "Good explanation."


def test_examiner_can_publish_complete_result_and_student_can_view_it(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    grade_response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={
            "awarded_marks": 4.0,
            "examiner_feedback": "Correct core concept; add an example.",
        },
    )
    assert grade_response.status_code == 200

    publish_response = client.post(
        f"/grading/sessions/{data['session'].id}/publish",
        headers=auth_headers(data["examiner"]),
        json={"grade": "Distinction"},
    )
    assert publish_response.status_code == 200
    assert publish_response.json()["published"] is True

    db_session.refresh(data["answer"])
    result = db_session.query(Result).filter(
        Result.session_id == data["session"].id,
    ).one()
    assert result.is_published is True
    assert result.published_at is not None
    assert result.grade == "Distinction"

    student_results = client.get(
        "/results/me",
        headers=auth_headers(data["student"]),
    )
    assert student_results.status_code == 200
    assert len(student_results.json()["results"]) == 1

    detail = client.get(
        f"/results/{data['session'].id}",
        headers=auth_headers(data["student"]),
    )
    assert detail.status_code == 200
    question_result = detail.json()["question_results"][0]
    assert question_result["outcome"] == "partial"
    assert question_result["examiner_feedback"] == "Correct core concept; add an example."


def test_published_result_cannot_be_changed(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    data["answer"].awarded_marks = 4.0
    db_session.commit()

    publish_response = client.post(
        f"/grading/sessions/{data['session'].id}/publish",
        headers=auth_headers(data["examiner"]),
    )
    assert publish_response.status_code == 200

    edit_response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={"awarded_marks": 2.0},
    )
    assert edit_response.status_code == 409


def test_examiner_can_list_submitted_sessions_for_review(
    client,
    grading_data,
):
    data = grading_data
    response = client.get(
        "/grading/sessions",
        headers=auth_headers(data["examiner"]),
    )
    assert response.status_code == 200
    sessions = response.json()["sessions"]
    assert any(item["session_id"] == data["session"].id for item in sessions)


def test_examiner_can_save_rubric_breakdown(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={
            "awarded_marks": 4.0,
            "rubric_scores": [
                {
                    "criterion": "Concept accuracy",
                    "description": "Explains the core concept.",
                    "max_marks": 3.0,
                    "awarded_marks": 2.5,
                },
                {
                    "criterion": "Organization",
                    "description": "Presents the information clearly.",
                    "max_marks": 2.0,
                    "awarded_marks": 1.5,
                },
            ],
        },
    )

    assert response.status_code == 200
    db_session.refresh(data["answer"])
    assert len(data["answer"].rubric_scores) == 2
    assert sum(
        item["awarded_marks"] for item in data["answer"].rubric_scores
    ) == pytest.approx(4.0)


def test_rubric_maximum_must_match_question_maximum(
    client,
    grading_data,
):
    data = grading_data
    response = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={
            "awarded_marks": 4.0,
            "rubric_scores": [
                {
                    "criterion": "Concept accuracy",
                    "max_marks": 4.0,
                    "awarded_marks": 4.0,
                }
            ],
        },
    )

    assert response.status_code == 400
    assert "maximum marks" in response.json()["detail"].lower()


def test_answer_marks_allow_three_evaluations_only(client, db_session, grading_data):
    data = grading_data
    initial_grade = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={"awarded_marks": 4.0},
    )
    assert initial_grade.status_code == 200

    for new_marks in (3.0, 2.0):
        response = client.post(
            f"/grading/answers/{data['answer'].id}/grade",
            headers=auth_headers(data["examiner"]),
            json={"awarded_marks": new_marks},
        )
        assert response.status_code == 200

    fourth_evaluation = client.post(
        f"/grading/answers/{data['answer'].id}/grade",
        headers=auth_headers(data["examiner"]),
        json={"awarded_marks": 0.5},
    )
    assert fourth_evaluation.status_code == 409

    history = client.get(
        f"/grading/answers/{data['answer'].id}/mark-revisions",
        headers=auth_headers(data["examiner"]),
    )
    assert history.status_code == 200
    assert history.json()["revisions_used"] == 2
    assert history.json()["evaluation_count"] == 3
    assert history.json()["revisions_remaining"] == 0
    assert [item["revision_number"] for item in history.json()["history"]] == [1, 2]


def test_examiner_can_view_face_photo_for_their_own_exam(client, db_session, grading_data):
    data = grading_data
    data["session"].face_capture_data = b"candidate-face-photo"
    data["session"].face_capture_mime_type = "image/jpeg"
    db_session.commit()

    response = client.get(
        f"/grading/sessions/{data['session'].id}/face-photo",
        headers=auth_headers(data["examiner"]),
    )
    assert response.status_code == 200
    assert response.content == b"candidate-face-photo"
    assert response.headers.get("cache-control") == "private, no-store"


def test_other_examiner_cannot_view_candidate_face_photo(client, db_session, grading_data):
    data = grading_data
    data["session"].face_capture_data = b"candidate-face-photo"
    data["session"].face_capture_mime_type = "image/jpeg"
    other_examiner = User(
        full_name="Other Examiner",
        email="other-grading-examiner@example.com",
        password_hash="test-password-hash",
        role="examiner",
        is_active=True,
    )
    db_session.add(other_examiner)
    db_session.commit()

    response = client.get(
        f"/grading/sessions/{data['session'].id}/face-photo",
        headers=auth_headers(other_examiner),
    )
    assert response.status_code == 403


def test_staff_can_view_student_answers_in_the_exact_paper_order(
    client,
    db_session,
    grading_data,
):
    data = grading_data
    admin = User(
        full_name="Read Only Admin",
        email="grading-review-admin@example.com",
        password_hash="test-password-hash",
        role="admin",
        is_active=True,
    )
    db_session.add(admin)
    db_session.commit()

    for staff_user in (data["examiner"], admin):
        response = client.get(
            f"/grading/sessions/{data['session'].id}/review",
            headers=auth_headers(staff_user),
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["student_name"] == data["student"].full_name
        assert payload["questions"][0]["question_order"] == 1
        assert payload["questions"][0]["question_id"] == data["question"].id
        assert payload["questions"][0]["answer_text"] == data["answer"].answer_text
        assert "positive_marks_earned" in payload
        assert "negative_marks_deducted" in payload
        assert "correct_questions" in payload
        assert "wrong_questions" in payload
        assert "exam_details" in payload
        assert "negative_marks" in payload["questions"][0]

def test_review_displays_selected_option_text_instead_of_only_option_ids(
    client, db_session, grading_data
):
    data = grading_data
    question = QuestionBank(
        question_text="What is 2 + 2?",
        question_type="MCQ",
        subject="Mathematics",
        difficulty="easy",
        marks=1,
        created_by=data["examiner"].id,
    )
    db_session.add(question)
    db_session.flush()
    correct_option = Option(
        question_id=question.id,
        option_text="4",
        is_correct=True,
    )
    db_session.add_all([
        correct_option,
        Option(question_id=question.id, option_text="5", is_correct=False),
    ])
    db_session.flush()
    session = ExamSession(
        exam_id=data["exam"].id,
        student_id=data["student"].id,
        started_at=datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=5),
        submitted_at=datetime.now(timezone.utc).replace(tzinfo=None),
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None),
        status="submitted",
        selected_question_ids=[question.id],
    )
    db_session.add(session)
    db_session.flush()
    db_session.add(Answer(
        session_id=session.id,
        question_id=question.id,
        answer_text=f"[{correct_option.id}]",
    ))
    db_session.commit()

    response = client.get(
        f"/grading/sessions/{session.id}/review",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 200
    assert response.json()["questions"][0]["selected_options"] == ["4"]

