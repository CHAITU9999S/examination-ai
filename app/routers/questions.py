
from fastapi import APIRouter, Depends, HTTPException
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


@router.post("/")
def create_question(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    try:
        validate_question(
            data.question_type,
            data.question_text,
            data.marks,
            data.options,
            data.negative_marks,
            data.correct_option_index,
            data.correct_option_indices
        )
    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    question = QuestionBank(
        question_text=data.question_text,
        question_type=data.question_type,
        subject=data.subject,
        difficulty=data.difficulty,
        expected_answer=data.expected_answer,
        model_answer_text=data.model_answer_text,
        marks=data.marks,
        negative_marks=data.negative_marks,
        tags=data.tags,
        created_by=current_user.id
    )

    db.add(question)
    db.flush()

    for index, option_text in enumerate(data.options):
        db.add(
            Option(
                question_id=question.id,
                option_text=option_text,
                is_correct=(
                    (
                        data.question_type == "MCQ"
                        and index == data.correct_option_index
                    )
                    or
                    (
                        data.question_type == "multi_select"
                        and index in (
                            data.correct_option_indices or []
                        )
                    )
                )
            )
        )

    db.commit()
    db.refresh(question)

    return {
        "message": "Question created successfully",
        "question_id": question.id
    }


@router.get("/")
def list_questions(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    questions = db.query(QuestionBank).all()

    question_ids = [question.id for question in questions]

    all_options = []

    if question_ids:
        all_options = db.query(Option).filter(
            Option.question_id.in_(question_ids)
        ).all()

    options_by_question = {}

    for option in all_options:
        options_by_question.setdefault(
            option.question_id, []
        ).append({
            "id": option.id,
            "option_text": option.option_text,
            "is_correct": option.is_correct
        })

    return [
        {
            "id": question.id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "subject": question.subject,
            "difficulty": question.difficulty,
            "expected_answer": question.expected_answer,
            "model_answer_text": question.model_answer_text,
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "tags": question.tags,
            "options": options_by_question.get(
                question.id, []
            )
        }
        for question in questions
    ]


@router.delete("/{question_id}")
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    db.delete(question)
    db.commit()

    return {
        "message": "Question deleted successfully"
    }
    
