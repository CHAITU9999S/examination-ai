import io
from datetime import datetime, timedelta, timezone

from PIL import Image

import pytest

from app.auth import create_access_token
from app.models import Answer, Exam, ExamSession, QuestionBank, Result, User


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


def test_ai_grading_is_disabled_without_explicit_opt_in(
    client,
    grading_data,
    monkeypatch,
):
    data = grading_data

    monkeypatch.setenv("AI_GRADING_ENABLED", "false")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key-not-used")

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
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["student"]),
    )

    assert response.status_code == 403


def test_ai_grading_rejects_image_upload_answers(
    client,
    db_session,
    grading_data,
    monkeypatch,
):
    data = grading_data
    data["question"].question_type = "image_upload"
    db_session.commit()
    monkeypatch.setenv("AI_GRADING_ENABLED", "true")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    response = client.post(
        f"/grading/answers/{data['answer'].id}/ai-suggestion",
        headers=auth_headers(data["examiner"]),
    )

    assert response.status_code == 400
    assert "short and long" in response.json()["detail"].lower()
