
import json
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Answer,
    ExamQuestion,
    ExamSession,
    Option,
    QuestionBank,
)


# ==========================================
# CONFIGURATION
# ==========================================

SHORT_ANSWER_MAX_WORDS = 1000
LONG_ANSWER_MAX_WORDS = 10000

OBJECTIVE_QUESTION_TYPES = {
    "MCQ",
    "multi_select",
}

TEXT_QUESTION_TYPES = {
    "short_answer",
    "long_answer",
}


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def _value(value):
    """Return the underlying value of an enum when applicable."""

    return getattr(value, "value", value)


def _get_role(user):
    """Get the user's role as a string."""

    return _value(user.role)


def _get_question_type(question):
    """Get the question type as a string."""

    return _value(question.question_type)


def _raise_error(code, message):
    """Raise a standard HTTP exception."""

    raise HTTPException(
        status_code=code,
        detail=message,
    )


def _validate_active_session(
    session: ExamSession,
    current_user,
):
    """Check ownership and whether the examination is still active."""

    if session.student_id != current_user.id:
        _raise_error(
            status.HTTP_403_FORBIDDEN,
            "You cannot access another student's examination session.",
        )

    if _get_role(current_user) != "student":
        _raise_error(
            status.HTTP_403_FORBIDDEN,
            "Only students can submit examination answers.",
        )

    if not current_user.is_active:
        _raise_error(
            status.HTTP_403_FORBIDDEN,
            "Your account is inactive.",
        )

    if session.status != "in_progress":
        _raise_error(
            status.HTTP_409_CONFLICT,
            "This examination session is no longer active.",
        )

    now = datetime.utcnow()

    if session.expires_at <= now:
        _raise_error(
            status.HTTP_409_CONFLICT,
            "The examination time has expired.",
        )


def _validate_question_assignment(
    db: Session,
    session: ExamSession,
    question: QuestionBank,
):
    """Verify that the question is assigned to the active examination."""

    assignment = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == session.exam_id,
        ExamQuestion.question_id == question.id,
    ).first()

    if assignment is None:
        _raise_error(
            status.HTTP_403_FORBIDDEN,
            "This question is not assigned to the examination.",
        )

    selected_ids = session.selected_question_ids

    if selected_ids is not None and question.id not in selected_ids:
        _raise_error(
            status.HTTP_403_FORBIDDEN,
            "This question is not part of your examination paper.",
        )


def _get_option_ids(
    db: Session,
    question_id: int,
):
    """Return all option IDs belonging to a question."""

    return {
        option.id
        for option in db.query(Option).filter(
            Option.question_id == question_id,
        ).all()
    }


def _validate_selected_options(
    db: Session,
    question: QuestionBank,
    selected_option_ids,
):
    """Validate selected options without revealing correct answers."""

    question_type = _get_question_type(question)

    if not isinstance(selected_option_ids, list):
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Selected options must be provided as a list.",
        )

    if question_type == "MCQ" and len(selected_option_ids) != 1:
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "MCQ requires exactly one selected option.",
        )

    if question_type == "multi_select" and not selected_option_ids:
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Select at least one option.",
        )

    if len(selected_option_ids) != len(set(selected_option_ids)):
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Duplicate option selections are not allowed.",
        )

    if any(
        isinstance(option_id, bool)
        or not isinstance(option_id, int)
        or option_id <= 0
        for option_id in selected_option_ids
    ):
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Selected option IDs must be positive integers.",
        )

    available_ids = _get_option_ids(
        db,
        question.id,
    )

    if not set(selected_option_ids).issubset(available_ids):
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "One or more selected options do not belong to this question.",
        )


def _validate_text_answer(
    question: QuestionBank,
    answer_text,
):
    """Validate text answer content and word limits."""

    if not isinstance(answer_text, str):
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Answer must be text.",
        )

    if not answer_text.strip():
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Answer cannot be empty.",
        )

    question_type = _get_question_type(question)

    if question_type == "short_answer":
        maximum_words = SHORT_ANSWER_MAX_WORDS

    else:
        maximum_words = LONG_ANSWER_MAX_WORDS

    word_count = len(answer_text.split())

    if word_count > maximum_words:
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            f"Answer exceeds the maximum limit of {maximum_words} words.",
        )


# ==========================================
# GET EXISTING ANSWER
# ==========================================

def get_student_answer(
    db: Session,
    session_id: int,
    question_id: int,
    current_user,
):
    """Retrieve the current student's saved answer."""

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()

    if session is None:
        _raise_error(
            status.HTTP_404_NOT_FOUND,
            "Examination session not found.",
        )

    if session.student_id != current_user.id:
        _raise_error(
            status.HTTP_403_FORBIDDEN,
            "You cannot access another student's answer.",
        )

    answer = db.query(Answer).filter(
        Answer.session_id == session_id,
        Answer.question_id == question_id,
    ).first()

    if answer is None:
        _raise_error(
            status.HTTP_404_NOT_FOUND,
            "No saved answer was found.",
        )

    return answer


# ==========================================
# SAVE OR UPDATE ANSWER
# ==========================================

def save_answer(
    db: Session,
    session_id: int,
    question_id: int,
    current_user,
    answer_text=None,
    selected_option_ids=None,
):
    """
    Save or update an answer during an active examination.

    Objective answers are stored as JSON option IDs in answer_text.
    Text answers are stored as ordinary text.

    Image-upload answers are handled separately by the file-upload
    workflow.
    """

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).with_for_update().first()

    if session is None:
        _raise_error(
            status.HTTP_404_NOT_FOUND,
            "Examination session not found.",
        )

    _validate_active_session(
        session,
        current_user,
    )

    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id,
    ).first()

    if question is None:
        _raise_error(
            status.HTTP_404_NOT_FOUND,
            "Question not found.",
        )

    _validate_question_assignment(
        db,
        session,
        question,
    )

    question_type = _get_question_type(question)

    if question_type in OBJECTIVE_QUESTION_TYPES:

        if answer_text is not None:
            _raise_error(
                status.HTTP_400_BAD_REQUEST,
                "Use selected_option_ids for objective questions.",
            )

        _validate_selected_options(
            db,
            question,
            selected_option_ids,
        )

        stored_answer = json.dumps(
            selected_option_ids,
        )

    elif question_type in TEXT_QUESTION_TYPES:

        if selected_option_ids is not None:
            _raise_error(
                status.HTTP_400_BAD_REQUEST,
                "Text questions do not accept selected options.",
            )

        _validate_text_answer(
            question,
            answer_text,
        )

        stored_answer = answer_text.strip()

    elif question_type == "image_upload":

        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Image questions must use the image-upload endpoint.",
        )

    else:
        _raise_error(
            status.HTTP_400_BAD_REQUEST,
            "Unsupported question type.",
        )

    try:
        answer = db.query(Answer).filter(
            Answer.session_id == session_id,
            Answer.question_id == question_id,
        ).with_for_update().first()

        if answer is None:
            answer = Answer(
                session_id=session_id,
                question_id=question_id,
                answer_text=stored_answer,
            )

            db.add(answer)

        else:
            answer.answer_text = stored_answer

        db.commit()
        db.refresh(answer)

        return answer

    except IntegrityError:
        db.rollback()

        _raise_error(
            status.HTTP_409_CONFLICT,
            "The answer could not be saved because of a database conflict.",
        )

    except SQLAlchemyError:
        db.rollback()

        _raise_error(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "Database error while saving the answer.",
        )


# ==========================================
# LIST SESSION ANSWERS
# ==========================================

def list_session_answers(
    db: Session,
    session_id: int,
    current_user,
):
    """List saved answers belonging to the current student's session."""

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()

    if session is None:
        _raise_error(
            status.HTTP_404_NOT_FOUND,
            "Examination session not found.",
        )

    if session.student_id != current_user.id:
        _raise_error(
            status.HTTP_403_FORBIDDEN,
            "You cannot access another student's answers.",
        )

    return db.query(Answer).filter(
        Answer.session_id == session_id,
    ).order_by(
        Answer.id.asc(),
    ).all()
