
from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    ExamQuestion,
    Option,
    QuestionBank,
    User,
)
from app.services.question_validation import validate_question


# ==========================================
# HELPERS
# ==========================================

def get_role_value(user: User) -> str:
    """Return a user's role as a string."""

    return getattr(user.role, "value", user.role)


def require_question_manager(user: User):
    """Allow only Admins and Examiners to manage questions."""

    if get_role_value(user) not in {"admin", "examiner"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators and examiners can manage questions.",
        )


def get_question_or_404(
    db: Session,
    question_id: int,
):
    """Retrieve a question or return a 404 response."""

    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id,
    ).first()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )

    return question


def ensure_question_not_assigned(
    db: Session,
    question_id: int,
):
    """Prevent deletion of a question already assigned to an exam."""

    assignment = db.query(ExamQuestion).filter(
        ExamQuestion.question_id == question_id,
    ).first()

    if assignment is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This question is assigned to an examination "
                "and cannot be deleted."
            ),
        )


# ==========================================
# CREATE QUESTION
# ==========================================

def create_question(
    db: Session,
    data,
    current_user: User,
):
    """Create a question and its options."""

    require_question_manager(current_user)

    question_type = getattr(
        data.question_type,
        "value",
        data.question_type,
    )

    options_data = getattr(data, "options", None)

    correct_option_index = getattr(
        data,
        "correct_option_index",
        None,
    )

    correct_option_indices = getattr(
        data,
        "correct_option_indices",
        None,
    )

    try:
        validate_question(
            question_type=question_type,
            question_text=data.question_text,
            marks=data.marks,
            options=options_data,
            negative_marks=getattr(data, "negative_marks", 0),
            correct_option_index=correct_option_index,
            correct_option_indices=correct_option_indices,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    try:
        question = QuestionBank(
            question_text=data.question_text.strip(),
            question_type=question_type,
            subject=getattr(data, "subject", None),
            difficulty=getattr(
                getattr(data, "difficulty", None),
                "value",
                getattr(data, "difficulty", None),
            ),
            expected_answer=getattr(data, "expected_answer", None),
            model_answer_text=getattr(
                data,
                "model_answer_text",
                None,
            ),
            marks=data.marks,
            negative_marks=getattr(data, "negative_marks", 0),
            tags=getattr(data, "tags", None),
            created_by=current_user.id,
        )

        db.add(question)
        db.flush()

        if question_type in {"MCQ", "multi_select"}:
            for index, option_data in enumerate(options_data):

                if isinstance(option_data, str):
                    option_text = option_data

                else:
                    option_text = option_data["text"]

                is_correct = (
                    index == correct_option_index
                    if question_type == "MCQ"
                    else index in (correct_option_indices or [])
                )

                option = Option(
                    question_id=question.id,
                    option_text=option_text.strip(),
                    is_correct=is_correct,
                )

                db.add(option)

        db.commit()
        db.refresh(question)

        return question

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question could not be created because of a database conflict.",
        )

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database error while creating the question.",
        )


# ==========================================
# GET SINGLE QUESTION
# ==========================================

def get_question(
    db: Session,
    question_id: int,
    current_user: User,
):
    """Retrieve one question for an authorized question manager."""

    require_question_manager(current_user)

    return get_question_or_404(
        db,
        question_id,
    )


# ==========================================
# LIST QUESTIONS
# ==========================================

def list_questions(
    db: Session,
    current_user: User,
    subject: str | None = None,
    difficulty: str | None = None,
    question_type: str | None = None,
    skip: int = 0,
    limit: int = 100,
):
    """List questions with optional filters."""

    require_question_manager(current_user)

    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip cannot be negative.",
        )

    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 500.",
        )

    query = db.query(QuestionBank)

    if subject:
        query = query.filter(
            QuestionBank.subject == subject,
        )

    if difficulty:
        query = query.filter(
            QuestionBank.difficulty == difficulty,
        )

    if question_type:
        query = query.filter(
            QuestionBank.question_type == question_type,
        )

    return query.order_by(
        QuestionBank.id.desc(),
    ).offset(skip).limit(limit).all()


# ==========================================
# UPDATE QUESTION
# ==========================================

def update_question(
    db: Session,
    question_id: int,
    updates: dict,
    current_user: User,
):
    """Update question details without replacing its database record."""

    require_question_manager(current_user)

    question = get_question_or_404(
        db,
        question_id,
    )

    allowed_fields = {
        "question_text",
        "subject",
        "difficulty",
        "expected_answer",
        "model_answer_text",
        "marks",
        "negative_marks",
        "tags",
    }

    unknown_fields = set(updates) - allowed_fields

    if unknown_fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more unsupported question fields were provided.",
        )

    for field, value in updates.items():

        if field == "question_text":
            if not isinstance(value, str) or not value.strip():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Question text cannot be empty.",
                )

            value = value.strip()

        elif field == "difficulty" and value is not None:
            value = getattr(value, "value", value)

            if value not in {"easy", "medium", "hard"}:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid question difficulty.",
                )

        elif field in {"marks", "negative_marks"}:
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
            ):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"{field} must be a valid number.",
                )

            if field == "marks" and value <= 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Marks must be greater than zero.",
                )

            if field == "negative_marks" and value < 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Negative marks cannot be below zero.",
                )

        setattr(question, field, value)

    try:
        db.commit()
        db.refresh(question)

        return question

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update the question.",
        )


# ==========================================
# DELETE QUESTION
# ==========================================

def delete_question(
    db: Session,
    question_id: int,
    current_user: User,
):
    """Delete an unassigned question."""

    require_question_manager(current_user)

    question = get_question_or_404(
        db,
        question_id,
    )

    ensure_question_not_assigned(
        db,
        question_id,
    )

    try:
        db.delete(question)
        db.commit()

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This question is referenced by existing examination "
                "records and cannot be deleted."
            ),
        )

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to delete the question.",
        )

    return {
        "message": "Question deleted successfully.",
        "question_id": question_id,
    }
