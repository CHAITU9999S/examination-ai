import math
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Answer, Exam, ExamSession, QuestionBank, Result, User
from app.services.evaluation_service import (
    calculate_session_result,
    evaluate_objective_answers,
)
from app.services.subjective_grading import (
    approve_subjective_marks,
    generate_ai_grading_suggestion,
)


router = APIRouter(
    prefix="/grading",
    tags=["Exam Grading"],
)


class ImageAnnotation(BaseModel):
    annotation_type: Literal["highlight", "comment"]
    x: float = Field(ge=0, le=100, allow_inf_nan=False)
    y: float = Field(ge=0, le=100, allow_inf_nan=False)
    width: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)
    height: float = Field(default=0, ge=0, le=100, allow_inf_nan=False)
    text: str = Field(min_length=1, max_length=500)


class ManualGradeSubmission(BaseModel):
    awarded_marks: float = Field(
        ge=0,
        allow_inf_nan=False,
    )
    examiner_feedback: str | None = Field(default=None, max_length=5000)
    image_annotations: list[ImageAnnotation] = Field(
        default_factory=list,
        max_length=50,
    )


class BulkGradeItem(ManualGradeSubmission):
    answer_id: int = Field(gt=0)


class BulkGradeSubmission(BaseModel):
    grades: list[BulkGradeItem] = Field(min_length=1, max_length=200)


def require_examiner_or_admin(user: User):
    """Allow only active examiners and administrators."""

    role = getattr(user.role, "value", user.role)

    if not user.is_active or role not in {"examiner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active examiners and administrators can access grading.",
        )


def get_authorized_exam(
    exam_id: int,
    current_user: User,
    db: Session,
):
    """Retrieve an exam the current examiner is allowed to manage."""

    exam = db.query(Exam).filter(
        Exam.id == exam_id,
    ).first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    role = getattr(current_user.role, "value", current_user.role)

    if role == "examiner" and exam.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only grade answers for your own examinations.",
        )

    return exam


def _get_submitted_answer_context(
    answer_id: int,
    current_user: User,
    db: Session,
):
    """Load and authorize an answer from a submitted examination."""

    answer = db.query(Answer).filter(
        Answer.id == answer_id,
    ).first()

    if answer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer not found.",
        )

    session = db.query(ExamSession).filter(
        ExamSession.id == answer.session_id,
    ).first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )

    exam = get_authorized_exam(
        session.exam_id,
        current_user,
        db,
    )

    if session.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted examination answers can be graded.",
        )

    question = db.query(QuestionBank).filter(
        QuestionBank.id == answer.question_id,
    ).first()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )

    return answer, session, exam, question


@router.get("/pending")
def get_all_pending_subjective_answers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List pending subjective answers for exams visible to this staff member."""
    require_examiner_or_admin(current_user)

    query = db.query(
        Answer,
        ExamSession,
        QuestionBank,
        Exam,
    ).join(
        ExamSession,
        Answer.session_id == ExamSession.id,
    ).join(
        QuestionBank,
        Answer.question_id == QuestionBank.id,
    ).join(
        Exam,
        ExamSession.exam_id == Exam.id,
    ).filter(
        ExamSession.status == "submitted",
        QuestionBank.question_type.in_([
            "short_answer",
            "long_answer",
            "image_upload",
        ]),
        Answer.awarded_marks.is_(None),
    )

    role = getattr(current_user.role, "value", current_user.role)
    if role == "examiner":
        query = query.filter(Exam.created_by == current_user.id)

    rows = query.order_by(
        ExamSession.submitted_at.asc(),
        Answer.id.asc(),
    ).all()

    return {
        "total_pending": len(rows),
        "answers": [
            {
                "answer_id": answer.id,
                "session_id": session.id,
                "student_id": session.student_id,
                "exam_id": exam.id,
                "exam_title": exam.title,
                "question_id": question.id,
                "question_text": question.question_text,
                "question_type": getattr(
                    question.question_type,
                    "value",
                    question.question_type,
                ),
                "answer_text": answer.answer_text,
                "image_path": answer.image_path,
                "image_url": (
                    f"/grading/answers/{answer.id}/image"
                    if answer.image_path
                    else None
                ),
                "thumbnail_url": (
                    f"/grading/answers/{answer.id}/image?thumbnail=true"
                    if answer.image_path
                    else None
                ),
                "marks": question.marks,
                "maximum_marks": question.marks,
                "awarded_marks": answer.awarded_marks,
                "ai_suggested_marks": answer.ai_suggested_marks,
                "ai_justification": answer.ai_justification,
                "ai_matched_points": answer.ai_matched_points or [],
                "ai_missed_points": answer.ai_missed_points or [],
                "ai_model": answer.ai_model,
                "ai_suggestion_generated_at": answer.ai_suggestion_generated_at,
                "submitted_at": session.submitted_at,
            }
            for answer, session, question, exam in rows
        ],
    }


@router.get("/exams/{exam_id}/pending")
def get_pending_subjective_answers(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List submitted subjective answers awaiting examiner grading."""

    require_examiner_or_admin(current_user)

    exam = get_authorized_exam(
        exam_id,
        current_user,
        db,
    )

    rows = db.query(
        Answer,
        ExamSession,
        QuestionBank,
    ).join(
        ExamSession,
        Answer.session_id == ExamSession.id,
    ).join(
        QuestionBank,
        Answer.question_id == QuestionBank.id,
    ).filter(
        ExamSession.exam_id == exam.id,
        ExamSession.status == "submitted",
        QuestionBank.question_type.in_([
            "short_answer",
            "long_answer",
            "image_upload",
        ]),
        Answer.awarded_marks.is_(None),
    ).order_by(
        ExamSession.submitted_at.asc(),
        Answer.id.asc(),
    ).all()

    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "total_pending": len(rows),
        "answers": [
            {
                "answer_id": answer.id,
                "session_id": session.id,
                "student_id": session.student_id,
                "question_id": question.id,
                "question_text": question.question_text,
                "question_type": getattr(
                    question.question_type,
                    "value",
                    question.question_type,
                ),
                "answer_text": answer.answer_text,
                "image_path": answer.image_path,
                "image_url": (
                    f"/grading/answers/{answer.id}/image"
                    if answer.image_path
                    else None
                ),
                "maximum_marks": question.marks,
                "model_answer": question.model_answer_text,
                "submitted_at": session.submitted_at,
            }
            for answer, session, question in rows
        ],
    }


@router.get("/answers/{answer_id}/image")
def get_subjective_answer_image(
    answer_id: int,
    thumbnail: bool = Query(default=False),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve an uploaded answer image to its authorized examiner or admin."""

    require_examiner_or_admin(current_user)

    answer, session, exam, question = _get_submitted_answer_context(
        answer_id,
        current_user,
        db,
    )

    if not answer.image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No image is attached to this answer.",
        )

    upload_root = Path(
        os.getenv("ANSWER_UPLOAD_DIR") or os.getenv("UPLOAD_DIRECTORY", "uploads")
    ).resolve()

    relative_path = Path(answer.image_path)

    if relative_path.is_absolute() or ".." in relative_path.parts:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer image not found.",
        )

    image_file = (upload_root / relative_path).resolve()

    if thumbnail:
        image_file = (
            upload_root
            / "answers"
            / "thumbnails"
            / f"{image_file.stem}.webp"
        ).resolve()

    if upload_root not in image_file.parents or not image_file.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Answer image not found.",
        )

    media_type, _ = mimetypes.guess_type(image_file.name)

    if media_type not in {
        "image/jpeg",
        "image/png",
        "image/webp",
        "image/tiff",
        "image/bmp",
        "image/webp",
    }:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Stored answer image has an unsupported format.",
        )

    return FileResponse(
        path=image_file,
        media_type=media_type,
    )


@router.post("/sessions/{session_id}/evaluate-objective")
def evaluate_session_objective_answers(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate all objective answers and calculate the current result."""

    require_examiner_or_admin(current_user)

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )

    get_authorized_exam(
        session.exam_id,
        current_user,
        db,
    )

    if session.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted examination sessions can be evaluated.",
        )

    try:
        objective_result = evaluate_objective_answers(
            db,
            session_id,
        )
        result = calculate_session_result(
            db,
            session_id,
        )

    except HTTPException:
        raise

    except ValueError as error:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        )

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to evaluate the examination answers.",
        )

    return {
        "message": "Objective answer evaluation completed.",
        "session_id": session_id,
        "objective_evaluation": objective_result,
        "result": result,
        "result_ready": result.get("status") == "evaluated",
    }


@router.get("/exams/{exam_id}/review-groups")
def get_examiner_review_groups(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return submitted subjective answers grouped by question."""
    pending = get_pending_subjective_answers(
        exam_id=exam_id,
        current_user=current_user,
        db=db,
    )
    groups = {}
    for answer in pending["answers"]:
        question_id = answer["question_id"]
        group = groups.setdefault(
            question_id,
            {
                "question_id": question_id,
                "question_text": answer["question_text"],
                "question_type": answer["question_type"],
                "maximum_marks": answer["maximum_marks"],
                "answers": [],
            },
        )
        group["answers"].append(answer)

    return {
        "exam_id": exam_id,
        "exam_title": pending["exam_title"],
        "total_pending": pending["total_pending"],
        "question_groups": list(groups.values()),
    }


@router.post("/answers/{answer_id}/grade")
def grade_subjective_answer(
    answer_id: int,
    submission: ManualGradeSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save examiner-awarded marks for a submitted subjective answer."""

    require_examiner_or_admin(current_user)

    answer, session, exam, question = _get_submitted_answer_context(
        answer_id,
        current_user,
        db,
    )

    existing_result = db.query(Result).filter(
        Result.session_id == session.id,
    ).first()
    if existing_result is not None and existing_result.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published results cannot be changed.",
        )

    question_type = getattr(
        question.question_type,
        "value",
        question.question_type,
    )

    if question_type not in {
        "short_answer",
        "long_answer",
        "image_upload",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual grading is only available for subjective answers.",
        )

    if submission.image_annotations and question_type != "image_upload":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Image annotations are allowed only for image answers.",
        )

    maximum_marks = float(question.marks or 0)

    if not math.isfinite(maximum_marks) or maximum_marks < 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question maximum marks are invalid.",
        )

    if submission.awarded_marks > maximum_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marks cannot exceed {maximum_marks}.",
        )

    try:
        locked_answer = db.query(Answer).filter(
            Answer.id == answer_id,
        ).with_for_update().first()

        if locked_answer is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Answer not found.",
            )

        locked_answer.awarded_marks = float(
            submission.awarded_marks
        )
        locked_answer.examiner_feedback = submission.examiner_feedback
        locked_answer.image_annotations = (
            [annotation.model_dump() for annotation in submission.image_annotations]
            if submission.image_annotations
            else None
        )
        db.commit()

        result = calculate_session_result(
            db,
            session.id,
        )

    except HTTPException:
        db.rollback()
        raise

    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the awarded marks.",
        )

    return {
        "message": "Answer graded successfully.",
        "answer_id": answer_id,
        "session_id": session.id,
        "question_id": question.id,
        "awarded_marks": submission.awarded_marks,
        "maximum_marks": maximum_marks,
        "result": result,
        "result_ready": result.get("status") == "evaluated",
    }


@router.post("/sessions/{session_id}/bulk-grade")
def bulk_grade_session_answers(
    session_id: int,
    submission: BulkGradeSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save a validated batch of examiner marks and feedback."""

    require_examiner_or_admin(current_user)
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )
    get_authorized_exam(session.exam_id, current_user, db)

    if session.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted examination sessions can be graded.",
        )

    existing_result = db.query(Result).filter(
        Result.session_id == session_id,
    ).first()
    if existing_result is not None and existing_result.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published results cannot be changed.",
        )

    answer_ids = [item.answer_id for item in submission.grades]
    if len(answer_ids) != len(set(answer_ids)):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="An answer can appear only once in a bulk grading request.",
        )

    try:
        for item in submission.grades:
            answer = db.query(Answer).filter(
                Answer.id == item.answer_id,
                Answer.session_id == session_id,
            ).with_for_update().first()
            if answer is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Answer {item.answer_id} does not belong to this session.",
                )

            question = db.query(QuestionBank).filter(
                QuestionBank.id == answer.question_id,
            ).first()
            if question is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Question for answer {item.answer_id} was not found.",
                )

            question_type = getattr(
                question.question_type,
                "value",
                question.question_type,
            )
            if question_type not in {
                "short_answer",
                "long_answer",
                "image_upload",
            }:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Bulk grading accepts subjective answers only.",
                )

            maximum_marks = float(question.marks or 0)
            if item.awarded_marks > maximum_marks:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Answer {item.answer_id}: marks cannot exceed {maximum_marks}.",
                )
            if item.image_annotations and question_type != "image_upload":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Image annotations are allowed only for image answers.",
                )

            answer.awarded_marks = float(item.awarded_marks)
            answer.examiner_feedback = item.examiner_feedback
            answer.image_annotations = (
                [annotation.model_dump() for annotation in item.image_annotations]
                if item.image_annotations
                else None
            )

        db.commit()
        result = calculate_session_result(db, session_id)
    except HTTPException:
        db.rollback()
        raise
    except SQLAlchemyError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save bulk grading.",
        )

    return {
        "message": "Bulk grading saved successfully.",
        "session_id": session_id,
        "graded_answer_count": len(submission.grades),
        "result": result,
        "result_ready": result.get("status") == "evaluated",
    }


@router.post("/sessions/{session_id}/publish")
def publish_session_result(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Publish a complete result so the student can view it."""

    require_examiner_or_admin(current_user)
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )
    get_authorized_exam(session.exam_id, current_user, db)

    if session.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted examination sessions can be published.",
        )

    try:
        calculated = calculate_session_result(db, session_id)
    except HTTPException:
        raise
    except (ValueError, SQLAlchemyError):
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The result could not be finalized.",
        )

    if calculated.get("status") != "evaluated":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Grade all subjective answers before publishing this result.",
        )

    result = db.query(Result).filter(
        Result.session_id == session_id,
    ).with_for_update().first()
    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The final result record was not created.",
        )

    if not result.is_published:
        result.is_published = True
        result.published_at = datetime.utcnow()
        db.commit()
        db.refresh(result)

    return {
        "message": "Result published successfully.",
        "session_id": session_id,
        "published": result.is_published,
        "published_at": result.published_at,
        "result": calculated,
    }


@router.post("/answers/{answer_id}/ai-suggestion")
def create_ai_grading_suggestion(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Generate an AI suggestion without saving or approving marks."""

    require_examiner_or_admin(current_user)

    return generate_ai_grading_suggestion(
        db=db,
        answer_id=answer_id,
        current_user=current_user,
    )


@router.post("/answers/{answer_id}/approve-ai")
def approve_ai_grading_suggestion(
    answer_id: int,
    submission: ManualGradeSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Save examiner-approved marks after AI-assisted review."""

    require_examiner_or_admin(current_user)

    answer, session, exam, question = _get_submitted_answer_context(
        answer_id,
        current_user,
        db,
    )

    existing_result = db.query(Result).filter(
        Result.session_id == session.id,
    ).first()
    if existing_result is not None and existing_result.is_published:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published results cannot be changed.",
        )

    question_type = getattr(
        question.question_type,
        "value",
        question.question_type,
    )

    if question_type not in {
        "short_answer",
        "long_answer",
        "image_upload",
    }:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="AI-assisted approval requires written or OCR-extracted answer text.",
        )

    approval = approve_subjective_marks(
        db=db,
        answer_id=answer_id,
        awarded_marks=submission.awarded_marks,
        current_user=current_user,
    )

    result = calculate_session_result(
        db,
        session.id,
    )

    return {
        **approval,
        "result": result,
        "result_ready": result.get("status") == "evaluated",
    }
