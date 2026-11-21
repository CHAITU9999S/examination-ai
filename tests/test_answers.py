
import io
import json
from datetime import datetime, timedelta, timezone

import pytest
from PIL import Image

from app.auth import create_exam_access_token
from app.models import (
    User,
    Exam,
    ExamSession,
    ExamQuestion,
    QuestionBank,
    Option,
    Answer,
)


@pytest.fixture
def answer_test_data(db_session):
    """Create a student, exam, session and assigned questions."""

    student = User(
        full_name="Answer Test Student",
        email="answerstudent@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )

    db_session.add(student)
    db_session.commit()
    db_session.refresh(student)

    exam = Exam(
        title="Answer Test Examination",
        subject="Programming",
        duration_minutes=30,
        total_questions=3,
        randomize_questions=False,
        negative_marking=True,
        start_time=None,
        end_time=None,
        created_by=None,
    )

    db_session.add(exam)
    db_session.commit()
    db_session.refresh(exam)

    mcq = QuestionBank(
        question_text="What is Python?",
        question_type="MCQ",
        subject="Programming",
        difficulty="easy",
        marks=2,
        negative_marks=0.5,
    )

    multi_select = QuestionBank(
        question_text="Select programming languages.",
        question_type="multi_select",
        subject="Programming",
        difficulty="medium",
        marks=3,
        negative_marks=1,
    )

    short_answer = QuestionBank(
        question_text="Define a variable.",
        question_type="short_answer",
        subject="Programming",
        difficulty="easy",
        marks=2,
        negative_marks=0,
    )

    db_session.add_all([
        mcq,
        multi_select,
        short_answer,
    ])

    db_session.commit()

    for question in (mcq, multi_select, short_answer):
        db_session.refresh(question)

        db_session.add(
            ExamQuestion(
                exam_id=exam.id,
                question_id=question.id,
            )
        )

    db_session.commit()

    options = [
        Option(
            question_id=mcq.id,
            option_text="Programming language",
            is_correct=True,
        ),
        Option(
            question_id=mcq.id,
            option_text="Operating system",
            is_correct=False,
        ),
        Option(
            question_id=multi_select.id,
            option_text="Python",
            is_correct=True,
        ),
        Option(
            question_id=multi_select.id,
            option_text="Java",
            is_correct=True,
        ),
        Option(
            question_id=multi_select.id,
            option_text="HTML",
            is_correct=False,
        ),
    ]

    db_session.add_all(options)
    db_session.commit()

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    session = ExamSession(
        exam_id=exam.id,
        student_id=student.id,
        started_at=now,
        expires_at=now + timedelta(minutes=30),
        status="in_progress",
        selected_question_ids=[
            mcq.id,
            multi_select.id,
            short_answer.id,
        ],
    )

    db_session.add(session)
    db_session.commit()
    db_session.refresh(session)

    token = create_exam_access_token(
        exam_id=exam.id,
        student_id=student.id,
        session_id=session.id,
        expires_at=session.expires_at,
    )

    return {
        "student": student,
        "exam": exam,
        "session": session,
        "mcq": mcq,
        "multi_select": multi_select,
        "short_answer": short_answer,
        "token": token,
    }


def exam_headers(token):
    """Build examination authorization headers."""

    return {
        "Authorization": f"Bearer {token}",
    }


def test_cannot_clear_answer_after_question_timer_expires(
    client,
    db_session,
    answer_test_data,
):
    data = answer_test_data
    assignment = db_session.query(ExamQuestion).filter(
        ExamQuestion.exam_id == data["exam"].id,
        ExamQuestion.question_id == data["mcq"].id,
    ).first()
    assignment.question_time_limit_seconds = 1

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    saved_answer = Answer(
        session_id=data["session"].id,
        question_id=data["mcq"].id,
        answer_text="1",
        question_started_at=now - timedelta(seconds=5),
        question_elapsed_seconds=1,
        is_locked=True,
    )
    db_session.add(saved_answer)
    db_session.commit()

    response = client.delete(
        f"/answers/{data['session'].id}/{data['mcq'].id}",
        headers=exam_headers(data["token"]),
    )

    assert response.status_code == 409
    still_saved = db_session.query(Answer).filter(
        Answer.session_id == data["session"].id,
        Answer.question_id == data["mcq"].id,
    ).first()
    assert still_saved is not None

def test_submit_valid_mcq_answer(
    client,
    db_session,
    answer_test_data,
):
    """A student can submit a valid MCQ option."""

    data = answer_test_data

    option = db_session.query(Option).filter(
        Option.question_id == data["mcq"].id,
        Option.is_correct.is_(True),
    ).first()

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": str(option.id),
        },
    )

    assert response.status_code in (200, 201)

    saved_answer = db_session.query(Answer).filter(
        Answer.session_id == data["session"].id,
        Answer.question_id == data["mcq"].id,
    ).first()

    assert saved_answer is not None


def test_submit_valid_multi_select_answer(
    client,
    db_session,
    answer_test_data,
):
    """A student can submit multiple selected options."""

    data = answer_test_data

    options = db_session.query(Option).filter(
        Option.question_id == data["multi_select"].id,
        Option.is_correct.is_(True),
    ).all()

    selected_ids = [option.id for option in options]

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["multi_select"].id,
            "answer_text": json.dumps(selected_ids),
        },
    )

    assert response.status_code in (200, 201)


def test_reject_invalid_option_id(
    client,
    answer_test_data,
):
    """A student cannot submit an option belonging to another question."""

    data = answer_test_data

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": "999999",
        },
    )

    assert response.status_code == 400


def test_reject_multiple_options_for_mcq(
    client,
    db_session,
    answer_test_data,
):
    """An MCQ must contain exactly one selected option."""

    data = answer_test_data

    options = db_session.query(Option).filter(
        Option.question_id == data["mcq"].id,
    ).all()

    selected_ids = [option.id for option in options]

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": json.dumps(selected_ids),
        },
    )

    assert response.status_code == 400


def test_reject_empty_multi_select_answer(
    client,
    answer_test_data,
):
    """A multi-select answer must contain at least one option."""

    data = answer_test_data

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["multi_select"].id,
            "answer_text": "[]",
        },
    )

    assert response.status_code == 400


def test_reject_unassigned_question(
    client,
    db_session,
    answer_test_data,
):
    """A student cannot answer a question not assigned to the exam."""

    data = answer_test_data

    unassigned = QuestionBank(
        question_text="Unassigned question",
        question_type="short_answer",
        subject="Programming",
        difficulty="easy",
        marks=2,
        negative_marks=0,
    )

    db_session.add(unassigned)
    db_session.commit()
    db_session.refresh(unassigned)

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": unassigned.id,
            "answer_text": "Sample answer",
        },
    )

    assert response.status_code == 403


def test_reject_answer_from_another_student(
    client,
    db_session,
    answer_test_data,
):
    """A student cannot submit answers to another student's session."""

    data = answer_test_data

    another_student = User(
        full_name="Another Student",
        email="anotherstudent@example.com",
        password_hash="test-password-hash",
        role="student",
        is_active=True,
    )

    db_session.add(another_student)
    db_session.commit()
    db_session.refresh(another_student)

    now = datetime.now(timezone.utc).replace(tzinfo=None)

    another_session = ExamSession(
        exam_id=data["exam"].id,
        student_id=another_student.id,
        started_at=now,
        expires_at=now + timedelta(minutes=30),
        status="in_progress",
        selected_question_ids=[data["mcq"].id],
    )

    db_session.add(another_session)
    db_session.commit()
    db_session.refresh(another_session)

    response = client.post(
        f"/answers/{another_session.id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": "1",
        },
    )

    assert response.status_code == 403


def test_reject_expired_session(
    client,
    db_session,
    answer_test_data,
):
    """An expired examination session cannot accept new answers."""

    data = answer_test_data

    data["session"].expires_at = (
        datetime.now(timezone.utc).replace(tzinfo=None)
        - timedelta(minutes=1)
    )

    db_session.commit()

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": "1",
        },
    )

    assert response.status_code in (400, 403, 409)


def test_reject_answer_after_submission(
    client,
    db_session,
    answer_test_data,
):
    """Submitted examination sessions cannot accept new answers."""

    data = answer_test_data

    data["session"].status = "submitted"
    data["session"].submitted_at = datetime.now(
        timezone.utc
    ).replace(tzinfo=None)

    db_session.commit()

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": "1",
        },
    )

    assert response.status_code in (400, 403, 409)


def test_student_can_update_existing_answer(
    client,
    db_session,
    answer_test_data,
):
    """Submitting another answer updates the existing answer."""

    data = answer_test_data

    options = db_session.query(Option).filter(
        Option.question_id == data["mcq"].id,
    ).all()

    first_response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": str(options[0].id),
        },
    )

    assert first_response.status_code in (200, 201)

    second_response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["mcq"].id,
            "answer_text": str(options[1].id),
        },
    )

    assert second_response.status_code in (200, 201)

    saved_answers = db_session.query(Answer).filter(
        Answer.session_id == data["session"].id,
        Answer.question_id == data["mcq"].id,
    ).all()

    assert len(saved_answers) == 1
    assert saved_answers[0].answer_text == json.dumps([options[1].id])


def test_reject_oversized_short_answer(
    client,
    answer_test_data,
):
    """Short answers exceeding the configured word limit are rejected."""

    data = answer_test_data

    oversized_answer = " ".join(
        ["answer"] * 1001
    )

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": data["short_answer"].id,
            "answer_text": oversized_answer,
        },
    )

    assert response.status_code == 400


def test_image_upload_question_rejects_text_submission(
    client,
    db_session,
    answer_test_data,
):
    """Image-upload questions cannot be answered through text submission."""

    data = answer_test_data

    image_question = QuestionBank(
        question_text="Upload a diagram.",
        question_type="image_upload",
        subject="Programming",
        difficulty="easy",
        marks=5,
        negative_marks=0,
    )

    db_session.add(image_question)
    db_session.commit()
    db_session.refresh(image_question)

    db_session.add(
        ExamQuestion(
            exam_id=data["exam"].id,
            question_id=image_question.id,
        )
    )

    data["session"].selected_question_ids.append(
        image_question.id
    )

    db_session.commit()

    response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={
            "question_id": image_question.id,
            "answer_text": "Text instead of image",
        },
    )

    assert response.status_code == 400


def test_image_answer_upload_stores_image_and_ocr_text(
    client,
    db_session,
    answer_test_data,
    monkeypatch,
    tmp_path,
):
    data = answer_test_data

    image_question = QuestionBank(
        question_text="Upload a handwritten answer.",
        question_type="image_upload",
        subject="Programming",
        difficulty="easy",
        marks=5,
        negative_marks=0,
    )
    db_session.add(image_question)
    db_session.commit()
    db_session.refresh(image_question)

    db_session.add(
        ExamQuestion(
            exam_id=data["exam"].id,
            question_id=image_question.id,
        )
    )
    data["session"].selected_question_ids.append(image_question.id)
    db_session.commit()

    image_buffer = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(
        image_buffer,
        format="PNG",
    )
    image_bytes = image_buffer.getvalue()

    monkeypatch.setenv(
        "ANSWER_UPLOAD_DIR",
        str(tmp_path),
    )
    monkeypatch.setattr(
        "app.routers.answers.extract_text_from_image",
        lambda image_data: {
            "success": True,
            "extracted_text": "A handwritten database answer.",
            "message": "Text extracted successfully.",
            "requires_manual_review": True,
        },
    )

    response = client.post(
        f"/answers/{data['session'].id}/upload",
        headers=exam_headers(data["token"]),
        data={"question_id": str(image_question.id)},
        files={
            "file": (
                "handwritten-answer.png",
                image_bytes,
                "image/png",
            )
        },
    )

    assert response.status_code == 201
    assert response.json()["image_uploaded"] is True
    assert response.json()["ocr_completed"] is True
    assert response.json()["requires_manual_review"] is True

    saved_answer = db_session.query(Answer).filter(
        Answer.session_id == data["session"].id,
        Answer.question_id == image_question.id,
    ).first()

    assert saved_answer is not None
    assert saved_answer.answer_text == "A handwritten database answer."
    assert saved_answer.image_path == "neon:image/png"
    assert saved_answer.image_data == image_bytes

def test_student_can_clear_saved_answer(
    client,
    db_session,
    answer_test_data,
):
    data = answer_test_data
    answer = Answer(
        session_id=data["session"].id,
        question_id=data["short_answer"].id,
        answer_text="An earlier response",
    )
    db_session.add(answer)
    db_session.commit()

    response = client.delete(
        f"/answers/{data['session'].id}/{data['short_answer'].id}",
        headers=exam_headers(data["token"]),
    )

    assert response.status_code == 200
    assert response.json()["deleted"] is True
    assert db_session.query(Answer).filter(
        Answer.session_id == data["session"].id,
        Answer.question_id == data["short_answer"].id,
    ).first() is None


def test_student_cannot_clear_unassigned_answer(
    client,
    db_session,
    answer_test_data,
):
    data = answer_test_data
    unassigned = QuestionBank(
        question_text="Not assigned",
        question_type="short_answer",
        marks=1,
    )
    db_session.add(unassigned)
    db_session.commit()
    db_session.refresh(unassigned)

    response = client.delete(
        f"/answers/{data['session'].id}/{unassigned.id}",
        headers=exam_headers(data["token"]),
    )

    assert response.status_code == 403



def test_question_timer_starts_once_and_locks_answer_after_time(client, db_session, answer_test_data):
    data = answer_test_data
    assignment = db_session.query(ExamQuestion).filter(
        ExamQuestion.exam_id == data["exam"].id,
        ExamQuestion.question_id == data["mcq"].id,
    ).one()
    assignment.question_time_limit_seconds = 60
    db_session.commit()

    first_response = client.get(
        f"/answers/{data['session'].id}/question-timer/{data['mcq'].id}",
        headers=exam_headers(data["token"]),
    )
    assert first_response.status_code == 200
    assert first_response.json()["question_time_limit_seconds"] == 60
    assert first_response.json()["remaining_seconds"] <= 60

    timer_answer = db_session.query(Answer).filter(
        Answer.session_id == data["session"].id,
        Answer.question_id == data["mcq"].id,
    ).one()
    original_start = timer_answer.question_started_at
    second_response = client.get(
        f"/answers/{data['session'].id}/question-timer/{data['mcq'].id}",
        headers=exam_headers(data["token"]),
    )
    db_session.refresh(timer_answer)
    assert second_response.status_code == 200
    assert timer_answer.question_started_at == original_start

    timer_answer.question_started_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=70)
    db_session.commit()
    expired_response = client.get(
        f"/answers/{data['session'].id}/question-timer/{data['mcq'].id}",
        headers=exam_headers(data["token"]),
    )
    assert expired_response.status_code == 200
    assert expired_response.json()["is_locked"] is True
    assert expired_response.json()["remaining_seconds"] == 0

    save_response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={"question_id": data["mcq"].id, "answer_text": "1"},
    )
    assert save_response.status_code == 409


def test_student_cannot_save_answer_while_exam_is_paused(client, answer_test_data):
    data = answer_test_data
    pause_response = client.post(
        f"/exam-sessions/pause/{data['session'].id}",
        headers=exam_headers(data["token"]),
    )
    assert pause_response.status_code == 200

    save_response = client.post(
        f"/answers/{data['session'].id}",
        headers=exam_headers(data["token"]),
        json={"question_id": data["mcq"].id, "answer_text": "1"},
    )
    assert save_response.status_code == 409
    assert "paused" in save_response.json()["detail"].lower()
