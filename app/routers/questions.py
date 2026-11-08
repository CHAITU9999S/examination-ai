from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import QuestionBank, Option
from app.schemas import QuestionCreate
from app.dependencies import require_role

router = APIRouter(prefix="/questions", tags=["Question Bank"])


@router.post("/")
def create_question(
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin"))
):
    if data.question_type in ["MCQ", "MULTI_SELECT"]:
        if len(data.options) < 2:
            raise HTTPException(
                status_code=400,
                detail="At least two options are required"
            )

    question = QuestionBank(
        question_text=data.question_text,
        question_type=data.question_type,
        subject=data.subject,
        difficulty=data.difficulty,
        expected_answer=data.expected_answer,
        marks=data.marks,
        negative_marks=data.negative_marks,
        tags=data.tags,
        created_by=current_user.id
    )

    db.add(question)
    db.flush()

    for option_text in data.options:
        db.add(Option(
            question_id=question.id,
            option_text=option_text
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
            "tags": q.tags
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
