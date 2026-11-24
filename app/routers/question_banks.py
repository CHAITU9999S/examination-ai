import io

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel, Field, ValidationError
from PIL import Image
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import Question, Option, ExamQuestion, ExamSession, Answer, Exam, User, AdminActivityLog
from app.question_bank_models import QuestionCollection, QuestionCollectionItem
from app.schemas import QuestionCreate
from app.services.question_validation import validate_question
from app.services.ocr_service import validate_image_bytes


router = APIRouter(prefix="/question-banks", tags=["Question Banks"])


class QuestionBankCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    subject: str | None = Field(default=None, max_length=100)


class ExamQuestionSelection(BaseModel):
    question_ids: list[int] = Field(default_factory=list)


def _get_bank(db: Session, bank_id: int):
    bank = db.query(QuestionCollection).filter(QuestionCollection.id == bank_id).first()
    if bank is None:
        raise HTTPException(status_code=404, detail="Question bank not found.")
    return bank


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
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Enter a question bank name.")
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


@router.get("/browse")
def browse_question_banks(
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    """Show all question banks without giving permission to change them."""
    rows = db.query(QuestionCollection, User).join(
        User, User.id == QuestionCollection.created_by
    ).order_by(QuestionCollection.id.desc()).all()
    result = []
    for bank, owner in rows:
        type_rows = db.query(Question.question_type).join(
            QuestionCollectionItem, QuestionCollectionItem.question_id == Question.id
        ).filter(QuestionCollectionItem.collection_id == bank.id).all()
        type_counts = {}
        for (question_type,) in type_rows:
            value = getattr(question_type, "value", question_type)
            type_counts[value] = type_counts.get(value, 0) + 1
        result.append({
            "id": bank.id, "name": bank.name, "description": bank.description,
            "subject": bank.subject, "question_count": len(type_rows),
            "question_types": type_counts, "created_by": owner.id,
            "created_by_name": owner.full_name, "created_by_role": owner.role,
            "created_at": bank.created_at,
        })
    return result


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
            "question_types": {
                getattr(question_type, "value", question_type): count
                for question_type, count in db.query(
                    Question.question_type,
                    func.count(Question.id),
                ).join(
                    QuestionCollectionItem,
                    QuestionCollectionItem.question_id == Question.id,
                ).filter(
                    QuestionCollectionItem.collection_id == bank.id,
                ).group_by(Question.question_type).all()
            },
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
    if not data.name.strip():
        raise HTTPException(status_code=400, detail="Enter a question bank name.")
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
    question_ids = [
        row[0] for row in db.query(QuestionCollectionItem.question_id).filter(
            QuestionCollectionItem.collection_id == bank.id
        ).all()
    ]
    db.query(QuestionCollectionItem).filter(
        QuestionCollectionItem.collection_id == bank.id
    ).delete(synchronize_session=False)

    for question_id in question_ids:
        question = db.query(Question).filter(Question.id == question_id).first()
        if question is None or question.created_by != current_user.id:
            continue
        if db.query(QuestionCollectionItem.id).filter(
            QuestionCollectionItem.question_id == question_id
        ).first():
            continue

        linked_rows = db.query(ExamQuestion).filter(
            ExamQuestion.question_id == question_id
        ).all()
        can_remove = True
        for linked_row in linked_rows:
            if db.query(ExamSession.id).filter(
                ExamSession.exam_id == linked_row.exam_id
            ).first():
                can_remove = False
                break
            linked_row.question_id = _copy_question_for_exam(
                db, question, current_user.id
            ).id

        if not can_remove or db.query(Answer.id).filter(
            Answer.question_id == question_id
        ).first():
            continue

        db.query(Question).filter(
            Question.source_question_id == question_id
        ).update({Question.source_question_id: None}, synchronize_session=False)
        db.delete(question)

    db.delete(bank)
    db.commit()
    return {"message": "Question bank deleted. Questions used in other banks, examinations, or student records were kept."}


@router.get("/{bank_id}/questions")
def list_bank_questions(
    bank_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_bank(db, bank_id)
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
            "expected_answer_image_available": bool(question.expected_answer_image_data),
            "options": [
                {"id": option.id, "option_text": option.option_text, "is_correct": option.is_correct}
                for option in options
            ],
        })
    return result


@router.post("/select-for-exam/{exam_id}", status_code=status.HTTP_201_CREATED)
def copy_selected_bank_questions_to_exam(
    exam_id: int,
    data: ExamQuestionSelection,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    """Copy selected questions from any staff question banks into an exam."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the examination creator can change its questions.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam.id).first():
        raise HTTPException(status_code=409, detail="Questions cannot change after a student exam session has been created.")
    question_ids = data.question_ids
    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(status_code=400, detail="Choose each question only once.")
    bank_question_ids = {row[0] for row in db.query(QuestionCollectionItem.question_id).filter(QuestionCollectionItem.question_id.in_(question_ids)).distinct().all()}
    if bank_question_ids != set(question_ids):
        raise HTTPException(status_code=400, detail="Some selected questions are not in a question bank.")
    source_rows = db.query(Question).filter(Question.id.in_(question_ids)).all()
    source_by_id = {question.id: question for question in source_rows}
    if len(source_by_id) != len(question_ids):
        raise HTTPException(status_code=404, detail="One or more selected questions could not be found.")
    selected_questions = [source_by_id[question_id] for question_id in question_ids]
    if exam.subject and any((question.subject or "").casefold() != exam.subject.casefold() for question in selected_questions):
        raise HTTPException(status_code=400, detail="All selected questions must match the examination subject.")
    # Add to the existing examination pool; never remove questions already added.
    existing_assignments = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam.id).all()
    existing_question_ids = [row.question_id for row in existing_assignments]
    existing_source_ids = {
        row[0] for row in db.query(Question.source_question_id).filter(
            Question.id.in_(existing_question_ids),
            Question.source_question_id.isnot(None),
        ).all()
    } if existing_question_ids else set()
    questions_to_add = [question for question in selected_questions if question.id not in existing_source_ids]
    next_order = max((row.question_order or 0 for row in existing_assignments), default=0) + 1
    # Source-bank marks never determine the maximum marks in this examination.
    # Minimum type/difficulty counts are enforced when student papers are generated.
    try:
        for order, source in enumerate(questions_to_add, start=next_order):
            copied = Question(
                question_text=source.question_text, question_type=source.question_type,
                subject=source.subject, difficulty=source.difficulty,
                expected_answer=source.expected_answer, model_answer_text=source.model_answer_text,
                question_image_path=source.question_image_path,
                question_image_data=source.question_image_data,
                question_image_mime_type=source.question_image_mime_type,
                expected_answer_image_data=source.expected_answer_image_data,
                expected_answer_image_mime_type=source.expected_answer_image_mime_type,
                marks=1.0, negative_marks=source.negative_marks,
                tags=list(source.tags or []), created_by=current_user.id,
                source_question_id=source.id,
            )
            db.add(copied)
            db.flush()
            for option in source.options:
                db.add(Option(question_id=copied.id, option_text=option.option_text, is_correct=option.is_correct))
            db.add(ExamQuestion(exam_id=exam.id, question_id=copied.id, question_order=order))
        db.add(AdminActivityLog(actor_user_id=current_user.id, action="exam_questions_copied_from_banks", details={"exam_id": exam.id, "source_question_ids": [question.id for question in questions_to_add], "question_count": len(questions_to_add)}))
        db.commit()
    except Exception:
        db.rollback()
        raise
    return {
        "message": (
            f"{len(questions_to_add)} question(s) added to this examination."
            if questions_to_add else
            "All selected questions are already present in this examination."
        ),
        "exam_id": exam.id,
        "question_count": len(questions_to_add),
        "total_question_count": len(existing_assignments) + len(questions_to_add),
    }


def _copy_question_for_exam(db: Session, source: Question, user_id: int):
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
        expected_answer_image_data=source.expected_answer_image_data,
        expected_answer_image_mime_type=source.expected_answer_image_mime_type,
        marks=source.marks,
        negative_marks=source.negative_marks,
        tags=list(source.tags or []),
        created_by=user_id,
        source_question_id=None,
    )
    db.add(copied)
    db.flush()
    for option in source.options:
        db.add(Option(question_id=copied.id, option_text=option.option_text, is_correct=option.is_correct))
    return copied


@router.post("/{bank_id}/questions/with-images", status_code=status.HTTP_201_CREATED)
async def add_question_to_bank_with_images(
    bank_id: int,
    question_data: str = Form(...),
    question_image: UploadFile | None = File(default=None),
    expected_answer_image: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    """Create a bank question and store its optional images in PostgreSQL."""

    bank = _get_owned_bank(db, bank_id, current_user.id)
    try:
        data = QuestionCreate.model_validate_json(question_data)
    except ValidationError as error:
        raise HTTPException(status_code=422, detail=str(error))

    async def read_image(upload: UploadFile | None):
        if upload is None:
            return None, None
        image_bytes = await upload.read(10 * 1024 * 1024 + 1)
        try:
            validate_image_bytes(image_bytes)
            image_format = Image.open(io.BytesIO(image_bytes)).format
        except HTTPException:
            raise
        except (OSError, ValueError):
            raise HTTPException(status_code=400, detail="Upload a valid image file.")
        mime_types = {
            "JPEG": "image/jpeg",
            "PNG": "image/png",
            "WEBP": "image/webp",
            "TIFF": "image/tiff",
            "BMP": "image/bmp",
        }
        media_type = mime_types.get(image_format)
        if media_type is None:
            raise HTTPException(status_code=415, detail="Supported image formats are JPEG, PNG, WEBP, TIFF and BMP.")
        return image_bytes, media_type

    prompt_image_data, prompt_image_mime = await read_image(question_image)
    expected_image_data, expected_image_mime = await read_image(expected_answer_image)

    question_type = getattr(data.question_type, "value", data.question_type)
    options = data.options or []
    try:
        validate_question(
            question_type,
            data.question_text or "",
            data.marks,
            options,
            data.negative_marks,
            data.correct_option_index,
            data.correct_option_indices,
            has_question_image=bool(prompt_image_data),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    if bank.subject and (data.subject or "").casefold() != bank.subject.casefold():
        raise HTTPException(status_code=400, detail="The question subject must match this question bank.")

    tags = list(data.tags or [])
    if data.topic and data.topic not in tags:
        tags.append(data.topic)

    question = Question(
        question_text=(data.question_text or "").strip(),
        question_type=question_type,
        subject=data.subject,
        difficulty=data.difficulty.value,
        expected_answer=data.expected_answer,
        model_answer_text=data.model_answer_text,
        question_image_path=f"neon:{prompt_image_mime}" if prompt_image_data else None,
        question_image_data=prompt_image_data,
        question_image_mime_type=prompt_image_mime,
        expected_answer_image_data=expected_image_data,
        expected_answer_image_mime_type=expected_image_mime,
        marks=data.marks,
        negative_marks=data.negative_marks,
        tags=tags,
        created_by=current_user.id,
    )
    try:
        db.add(question)
        db.flush()
        for index, option_text in enumerate(options):
            is_correct = (
                question_type == "MCQ" and index == data.correct_option_index
            ) or (
                question_type == "multi_select" and index in (data.correct_option_indices or [])
            )
            db.add(Option(question_id=question.id, option_text=option_text, is_correct=is_correct))
        db.add(QuestionCollectionItem(collection_id=bank.id, question_id=question.id))
        db.commit()
        db.refresh(question)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="The question could not be saved.")
    return {
        "message": "Question added to the question bank.",
        "question_id": question.id,
        "question_image_available": bool(prompt_image_data),
        "expected_answer_image_available": bool(expected_image_data),
        "storage": "neon_postgresql",
    }


@router.patch("/{bank_id}/questions/{question_id}")
def update_bank_question(
    bank_id: int,
    question_id: int,
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    question = db.query(Question).join(
        QuestionCollectionItem, QuestionCollectionItem.question_id == Question.id
    ).filter(
        QuestionCollectionItem.collection_id == bank.id,
        Question.id == question_id,
        Question.created_by == current_user.id,
    ).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found in your question bank.")

    question_type = getattr(data.question_type, "value", data.question_type)
    options = data.options or []
    try:
        validate_question(question_type, data.question_text, data.marks, options,
            data.negative_marks, data.correct_option_index, data.correct_option_indices,
            has_question_image=bool(question.question_image_path))
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    if bank.subject and (data.subject or "").casefold() != bank.subject.casefold():
        raise HTTPException(status_code=400, detail="The question subject must match this question bank.")

    # Older examinations may still point directly to a bank question. Give
    # those examinations their own copy before changing the original question.
    linked_rows = db.query(ExamQuestion).filter(ExamQuestion.question_id == question.id).all()
    for linked_row in linked_rows:
        if db.query(ExamSession.id).filter(ExamSession.exam_id == linked_row.exam_id).first():
            raise HTTPException(status_code=409, detail="This question is used by an examination that already has student sessions and cannot be changed safely.")
        linked_row.question_id = _copy_question_for_exam(db, question, current_user.id).id

    tags = list(data.tags or [])
    if data.topic and data.topic not in tags:
        tags.append(data.topic)
    question.question_text = (data.question_text or "").strip()
    question.question_type = question_type
    question.subject = data.subject
    question.difficulty = data.difficulty.value
    question.expected_answer = data.expected_answer
    question.model_answer_text = data.model_answer_text
    question.marks = data.marks
    question.negative_marks = data.negative_marks
    question.tags = tags
    db.query(Option).filter(Option.question_id == question.id).delete(synchronize_session=False)
    for index, option_text in enumerate(options):
        correct = (question_type == "MCQ" and index == data.correct_option_index) or (question_type == "multi_select" and index in (data.correct_option_indices or []))
        db.add(Option(question_id=question.id, option_text=option_text, is_correct=correct))
    db.commit()
    return {"message": "Question updated in your question bank.", "question_id": question.id}


@router.delete("/{bank_id}/questions/{question_id}/delete")
def delete_bank_question(
    bank_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin", "examiner")),
):
    bank = _get_owned_bank(db, bank_id, current_user.id)
    question = db.query(Question).join(
        QuestionCollectionItem, QuestionCollectionItem.question_id == Question.id
    ).filter(
        QuestionCollectionItem.collection_id == bank.id,
        Question.id == question_id,
        Question.created_by == current_user.id,
    ).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found in your question bank.")
    if db.query(Answer.id).filter(Answer.question_id == question.id).first():
        raise HTTPException(status_code=409, detail="This question is linked to student answers and cannot be deleted.")

    linked_rows = db.query(ExamQuestion).filter(ExamQuestion.question_id == question.id).all()
    for linked_row in linked_rows:
        if db.query(ExamSession.id).filter(ExamSession.exam_id == linked_row.exam_id).first():
            raise HTTPException(status_code=409, detail="This question is used by an examination that already has student sessions and cannot be deleted safely.")
        linked_row.question_id = _copy_question_for_exam(db, question, current_user.id).id

    # Older snapshots may keep a source reference. The copied question stays
    # unchanged, while the original can be deleted from the question banks.
    db.query(Question).filter(Question.source_question_id == question.id).update(
        {Question.source_question_id: None}, synchronize_session=False
    )
    db.query(QuestionCollectionItem).filter(
        QuestionCollectionItem.question_id == question.id
    ).delete(synchronize_session=False)
    db.delete(question)
    db.commit()
    return {"message": "Question deleted from your question banks. Existing examination copies were kept."}


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

    if bank.subject and (data.subject or "").casefold() != bank.subject.casefold():
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
            expected_answer_image_data=source.expected_answer_image_data,
            expected_answer_image_mime_type=source.expected_answer_image_mime_type,
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
