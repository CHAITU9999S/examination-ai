from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import QuestionBank, Option
from app.schemas import QuestionCreate
from app.dependencies import require_role
from app.services.question_validation import validate_question


router = APIRouter(
    prefix="/questions",
    tags=["Question Bank"]
)


# ==========================================
# CREATE QUESTION
# ==========================================

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_question(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    question_type = getattr(
        data.question_type,
        "value",
        data.question_type
    )

    options = data.options or []

    try:
        validate_question(
            question_type,
            data.question_text,
            data.marks,
            options,
            data.negative_marks,
            data.correct_option_index,
            data.correct_option_indices
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    # Preserve topic information using the existing tags column.
    tags = list(data.tags or [])

    if data.topic and data.topic not in tags:
        tags.append(data.topic)

    question = QuestionBank(
        question_text=data.question_text,
        question_type=question_type,
        subject=data.subject,
        difficulty=data.difficulty.value,
        expected_answer=data.expected_answer,
        model_answer_text=data.model_answer_text,
        marks=data.marks,
        negative_marks=data.negative_marks,
        tags=tags,
        created_by=current_user.id
    )

    try:
        db.add(question)
        db.flush()

        for index, option_text in enumerate(options):
            is_correct = (
                question_type == "MCQ"
                and index == data.correct_option_index
            ) or (
                question_type == "multi_select"
                and index in (data.correct_option_indices or [])
            )

            db.add(
                Option(
                    question_id=question.id,
                    option_text=option_text,
                    is_correct=is_correct
                )
            )

        db.commit()
        db.refresh(question)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The question could not be saved because of a database constraint."
        )

    except Exception:
        db.rollback()
        raise

    return {
        "message": "Question created successfully",
        "question_id": question.id
    }


# ==========================================
# LIST QUESTIONS
# ==========================================

@router.get("/")
def list_questions(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    questions = db.query(QuestionBank).order_by(
        QuestionBank.id
    ).all()

    question_ids = [
        question.id for question in questions
    ]

    all_options = []

    if question_ids:
        all_options = db.query(Option).filter(
            Option.question_id.in_(question_ids)
        ).order_by(
            Option.id
        ).all()

    options_by_question = {}

    for option in all_options:
        options_by_question.setdefault(
            option.question_id,
            []
        ).append({
            "id": option.id,
            "option_text": option.option_text,
            "is_correct": option.is_correct
        })

    return [
        {
            "id": question.id,
            "question_text": question.question_text,
            "question_type": getattr(
                question.question_type,
                "value",
                question.question_type
            ),
            "subject": question.subject,
            "difficulty": question.difficulty,
            "expected_answer": question.expected_answer,
            "model_answer_text": question.model_answer_text,
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "tags": question.tags or [],
            "options": options_by_question.get(
                question.id,
                []
            )
        }
        for question in questions
    ]


# ==========================================
# DELETE QUESTION
# ==========================================

@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id
    ).first()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found."
        )

    try:
        db.delete(question)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This question is linked to an examination or existing "
                "records and cannot be deleted safely."
            )
        )

    return {
        "message": "Question deleted successfully."
}
    
