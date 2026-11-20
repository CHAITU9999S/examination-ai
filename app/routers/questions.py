import io
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, Response
from PIL import Image
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import QuestionBank, Option, ExamQuestion, Exam, ExamSession
from app.schemas import QuestionCreate
from app.dependencies import require_role
from app.services.question_validation import validate_question
from app.services.ocr_service import validate_image_bytes


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
    query = db.query(QuestionBank)
    if current_user.role == "examiner":
        query = query.filter(QuestionBank.created_by == current_user.id)
    questions = query.order_by(QuestionBank.id).all()

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
            "question_image_available": bool(question.question_image_path),
            "tags": question.tags or [],
            "options": options_by_question.get(
                question.id,
                []
            )
        }
        for question in questions
    ]


# ==========================================
# UPLOAD QUESTION PROMPT IMAGE
# ==========================================

@router.post("/{question_id}/image", status_code=status.HTTP_201_CREATED)
async def upload_question_image(
    question_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Store an optional image that forms part of a question prompt."""

    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id
    ).first()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )
    if question.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the question creator can change its prompt image.",
        )

    linked_exam_ids = [
        row[0] for row in db.query(ExamQuestion.exam_id).filter(
            ExamQuestion.question_id == question_id
        ).all()
    ]
    if linked_exam_ids and db.query(ExamSession.id).filter(
        ExamSession.exam_id.in_(linked_exam_ids)
    ).first():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A question prompt image cannot be changed after a linked examination session has been created.",
        )

    image_bytes = await file.read(10 * 1024 * 1024 + 1)
    validate_image_bytes(image_bytes)

    try:
        image_format = Image.open(io.BytesIO(image_bytes)).format
    except (OSError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is not a valid image.",
        )

    extensions = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
        "TIFF": ".tiff",
        "BMP": ".bmp",
    }
    extension = extensions.get(image_format)

    if extension is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image format.",
        )

    mime_types = {
        "JPEG": "image/jpeg",
        "PNG": "image/png",
        "WEBP": "image/webp",
        "TIFF": "image/tiff",
        "BMP": "image/bmp",
    }
    media_type = mime_types.get(image_format)
    if media_type is None:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported image format.",
        )

    question.question_image_data = image_bytes
    question.question_image_mime_type = media_type
    question.question_image_path = f"neon:{media_type}"

    try:
        db.commit()
        db.refresh(question)
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the question image in Neon.",
        )

    return {
        "message": "Question image stored in Neon successfully.",
        "question_id": question.id,
        "image_uploaded": True,
        "storage": "neon_postgresql",
    }


# ==========================================
# GET QUESTION PROMPT IMAGE
# ==========================================

@router.get("/{question_id}/image")
def get_question_image(
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Return a question image from Neon to an authenticated examiner or admin."""

    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id
    ).first()

    if question is None or not question.question_image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question image not found.",
        )
    if (
        current_user.role == "examiner"
        and question.created_by != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can view prompt images only for questions you created.",
        )

    if question.question_image_data:
        return Response(
            content=question.question_image_data,
            media_type=question.question_image_mime_type or "application/octet-stream",
            headers={"Cache-Control": "private, no-store"},
        )

    # Backward compatibility for images uploaded before Neon binary storage.
    if question.question_image_path.startswith("neon:"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored question image data is unavailable.",
        )

    upload_root = Path(
        os.getenv("QUESTION_UPLOAD_DIR")
        or os.getenv("UPLOAD_DIRECTORY", "uploads")
    ).resolve()
    image_path = (upload_root / question.question_image_path).resolve()

    if not image_path.is_relative_to(upload_root) or not image_path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question image file is unavailable.",
        )

    return FileResponse(image_path)



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
    if question.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the question creator can delete this question.",
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
    
