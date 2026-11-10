
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import QuestionBank, Option
from app.schemas import QuestionCreate
from app.dependencies import require_role
from app.services.question_validation import validate_question

router = APIRouter(prefix="/questions", tags=["Question Bank"])


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
        raise HTTPException(status_code=400, detail=str(error))

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
        db.add(Option(
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
                    and index in (data.correct_option_indices or [])
                )
            )
        ))

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

    return [
        {
            "id": q.id,
            "question_text": q.question_text,
            "question_type": q.question_type,
            "subject": q.subject,
            "difficulty": q.difficulty,
            "marks": q.marks,
            "negative_marks": q.negative_marks,
            "tags": q.tags,
            "model_answer_text": q.model_answer_text
        }
        for q in questions
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

    return {"message": "Question deleted successfully"}
    
