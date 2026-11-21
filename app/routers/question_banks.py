from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import Question, Option, ExamQuestion, ExamSession, Answer
from app.question_bank_models import QuestionCollection, QuestionCollectionItem
from app.schemas import QuestionCreate
from app.services.question_validation import validate_question


router = APIRouter(prefix="/question-banks", tags=["Question Banks"])


class QuestionBankCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    subject: str | None = Field(default=None, max_length=100)


def _get_owned_bank(db: Session, bank_id: int, user_id: int):
    bank = db.query(QuestionCollection).filter(
        QuestionCollection.id == bank_id,
        QuestionCollection.created_by == user_id,
    ).first()
    if bank is None:
        raise HTTPException(status_code=404, detail="Question bank not found.")
    return bank


@router.post("/", status_code=status.HTTP_201_CREATED)
def create_question_bank(
    data: QuestionBankCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = QuestionCollection(
        name=data.name.strip(),
        description=data.description,
        subject=data.subject,
        created_by=current_user.id,
    )
    db.add(bank)
    db.commit()
    db.refresh(bank)
    return {"message": "Question bank created.", "bank_id": bank.id}


@router.get("/")
def list_question_banks(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    banks = db.query(QuestionCollection).filter(
        QuestionCollection.created_by == current_user.id
    ).order_by(QuestionCollection.id.desc()).all()

    return [
        {
            "id": bank.id,
            "name": bank.name,
            "description": bank.description,
            "subject": bank.subject,
            "question_count": db.query(QuestionCollectionItem.id).filter(
                QuestionCollectionItem.collection_id == bank.id
            ).count(),
            "created_at": bank.created_at,
        }
        for bank in banks
    ]


@router.patch("/{bank_id}")
def update_question_bank(
    bank_id: int,
    data: QuestionBankCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    bank.name = data.name.strip()
    bank.description = data.description
    bank.subject = data.subject
    db.commit()
    return {"message": "Question bank updated."}


@router.delete("/{bank_id}")
def delete_question_bank(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    db.query(QuestionCollectionItem).filter(
        QuestionCollectionItem.collection_id == bank.id
    ).delete(synchronize_session=False)
    db.delete(bank)
    db.commit()
    return {"message": "Question bank deleted. Saved questions and examination records were kept."}


@router.get("/{bank_id}/questions")
def list_bank_questions(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    rows = db.query(QuestionCollectionItem, Question).join(
        Question, Question.id == QuestionCollectionItem.question_id
    ).filter(QuestionCollectionItem.collection_id == bank.id).order_by(
        QuestionCollectionItem.id
    ).all()

    result = []
    for item, question in rows:
        options = db.query(Option).filter(Option.question_id == question.id).order_by(Option.id).all()
        result.append({
            "id": question.id,
            "question_text": question.question_text,
            "question_type": getattr(question.question_type, "value", question.question_type),
            "subject": question.subject,
            "difficulty": question.difficulty,
            "expected_answer": question.expected_answer,
            "model_answer_text": question.model_answer_text,
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "tags": question.tags or [],
            "question_image_available": bool(question.question_image_path),
            "options": [
                {"id": option.id, "option_text": option.option_text, "is_correct": option.is_correct}
                for option in options
            ],
        })
    return result


@router.post("/{bank_id}/questions", status_code=status.HTTP_201_CREATED)
def add_question_to_bank(
    bank_id: int,
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    question_type = getattr(data.question_type, "value", data.question_type)
    options = data.options or []
    try:
        validate_question(
            question_type, data.question_text, data.marks, options,
            data.negative_marks, data.correct_option_index,
            data.correct_option_indices,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if bank.subject and data.subject.casefold() != bank.subject.casefold():
        raise HTTPException(status_code=400, detail="The question subject must match this question bank.")

    tags = list(data.tags or [])
    if data.topic and data.topic not in tags:
        tags.append(data.topic)

    question = Question(
        question_text=data.question_text,
        question_type=question_type,
        subject=data.subject,
        difficulty=data.difficulty.value,
        expected_answer=data.expected_answer,
        model_answer_text=data.model_answer_text,
        marks=data.marks,
        negative_marks=data.negative_marks,
        tags=tags,
        created_by=current_user.id,
    )
    try:
        db.add(question)
        db.flush()
        for index, option_text in enumerate(options):
            correct = (
                question_type == "MCQ" and index == data.correct_option_index
            ) or (
                question_type == "multi_select" and index in (data.correct_option_indices or [])
            )
            db.add(Option(question_id=question.id, option_text=option_text, is_correct=correct))
        db.add(QuestionCollectionItem(collection_id=bank.id, question_id=question.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The question could not be saved.")
    return {"message": "Question added to the question bank.", "question_id": question.id}


@router.post("/{bank_id}/questions/{question_id}")
def add_existing_question_to_bank(
    bank_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    question = db.query(Question).filter(
        Question.id == question_id,
        Question.created_by == current_user.id,
    ).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    if bank.subject and question.subject and bank.subject.casefold() != question.subject.casefold():
        raise HTTPException(status_code=400, detail="The question subject must match this question bank.")
    if db.query(QuestionCollectionItem.id).filter_by(collection_id=bank.id, question_id=question.id).first():
        raise HTTPException(status_code=409, detail="This question is already in the question bank.")
    db.add(QuestionCollectionItem(collection_id=bank.id, question_id=question.id))
    db.commit()
    return {"message": "Question added to the question bank."}


@router.delete("/{bank_id}/questions/{question_id}")
def remove_question_from_bank(
    bank_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    item = db.query(QuestionCollectionItem).filter_by(
        collection_id=bank.id, question_id=question_id
    ).first()
    if item is None:
        raise HTTPException(status_code=404, detail="Question is not in this bank.")
    db.delete(item)
    db.commit()
    return {"message": "Question removed from this bank. The saved question was kept."}


@router.post("/{bank_id}/use-in-exam/{exam_id}")
def use_bank_questions_in_exam(
    bank_id: int,
    exam_id: int,
    question_ids: list[int],
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    from app.models import Exam

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the examination creator can change its questions.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam.id).first():
        raise HTTPException(status_code=409, detail="Questions cannot change after a student exam session has been created.")
    if not question_ids or len(question_ids) != len(set(question_ids)):
        raise HTTPException(status_code=400, detail="Choose one or more different questions.")
    if len(question_ids) < exam.total_questions:
        raise HTTPException(status_code=400, detail="Choose at least the examination question count.")
    items = db.query(QuestionCollectionItem).filter(
        QuestionCollectionItem.collection_id == bank.id,
        QuestionCollectionItem.question_id.in_(question_ids),
    ).all()
    if len(items) != len(question_ids):
        raise HTTPException(status_code=400, detail="Some selected questions are not in this question bank.")
    source_questions = db.query(Question).filter(
        Question.id.in_(question_ids),
        Question.created_by == current_user.id,
    ).all()
    if len(source_questions) != len(question_ids):
        raise HTTPException(status_code=403, detail="You can use only questions you created.")
    if exam.subject and any((q.subject or "").casefold() != exam.subject.casefold() for q in source_questions):
        raise HTTPException(status_code=400, detail="All selected questions must match the examination subject.")

    db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).delete(synchronize_session=False)
    for order, source in enumerate(source_questions, start=1):
        copied = Question(
            question_text=source.question_text,
            question_type=source.question_type,
            subject=source.subject,
            difficulty=source.difficulty,
            expected_answer=source.expected_answer,
            model_answer_text=source.model_answer_text,
            question_image_path=source.question_image_path,
            question_image_data=source.question_image_data,
            question_image_mime_type=source.question_image_mime_type,
            marks=source.marks,
            negative_marks=source.negative_marks,
            tags=source.tags,
            created_by=current_user.id,
            source_question_id=source.id,
        )
        db.add(copied)
        db.flush()
        for option in source.options:
            db.add(Option(question_id=copied.id, option_text=option.option_text, is_correct=option.is_correct))
        db.add(ExamQuestion(exam_id=exam.id, question_id=copied.id, question_order=order))
    db.commit()
    return {"message": "Selected questions were copied into the examination.", "exam_id": exam.id, "question_count": len(source_questions)}
