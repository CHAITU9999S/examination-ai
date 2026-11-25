import json
import math
import mimetypes
import os
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import AdminActivityLog, Answer, AnswerMarkRevision, Exam, ExamQuestion, ExamSession, QuestionBank, Result, User
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


class RubricScore(BaseModel):
    criterion: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=1000)
    max_marks: float = Field(gt=0, allow_inf_nan=False)
    awarded_marks: float = Field(ge=0, allow_inf_nan=False)


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
    rubric_scores: list[RubricScore] = Field(
        default_factory=list,
        max_length=30,
    )


class BulkGradeItem(ManualGradeSubmission):
    answer_id: int = Field(gt=0)


class BulkGradeSubmission(BaseModel):
    grades: list[BulkGradeItem] = Field(min_length=1, max_length=200)


class PublishResultRequest(BaseModel):
    grade: str | None = Field(default=None, max_length=20)


def require_examiner_or_admin(user: User):
    """Allow only active examiners and administrators."""

    role = getattr(user.role, "value", user.role)

    if not user.is_active or role not in {"examiner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only active examiners and administrators can access grading.",
        )


def get_visible_exam(
    exam_id: int,
    current_user: User,
    db: Session,
):
    """Find an exam that this staff member is allowed to view."""

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
            detail="You can only view your own examinations.",
        )

    return exam


def get_authorized_exam(
    exam_id: int,
    current_user: User,
    db: Session,
):
    """Find an exam this staff member is allowed to change."""

    exam = get_visible_exam(exam_id, current_user, db)

    if exam.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only change marks for examinations you created.",
        )

    return exam


@router.get("/sessions/{session_id}/face-photo")
def get_session_face_photo(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve the candidate's captured still photo to authorized exam staff."""
    require_examiner_or_admin(current_user)
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Examination session not found.")
    get_visible_exam(session.exam_id, current_user, db)
    if not session.face_capture_data:
        raise HTTPException(status_code=404, detail="No face capture is available for this session.")
    return Response(
        content=session.face_capture_data,
        media_type=session.face_capture_mime_type or "image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )


def _validate_rubric_scores(question, rubric_scores, awarded_marks):
    """Validate a per-criterion rubric and ensure its total matches final marks."""
    if not rubric_scores:
        return None

    criterion_names = [item.criterion.strip().casefold() for item in rubric_scores]
    if len(criterion_names) != len(set(criterion_names)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rubric criteria must be unique.",
        )

    maximum_total = sum(float(item.max_marks) for item in rubric_scores)
    awarded_total = sum(float(item.awarded_marks) for item in rubric_scores)
    question_maximum = float(question.marks or 0)

    if not math.isclose(maximum_total, question_maximum, rel_tol=0, abs_tol=0.01):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Rubric maximum marks must add up to the question's maximum marks.",
        )

    for item in rubric_scores:
        if item.awarded_marks > item.max_marks:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Rubric marks for '{item.criterion}' exceed its maximum.",
            )

    if not math.isclose(awarded_total, float(awarded_marks), rel_tol=0, abs_tol=0.01):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The sum of rubric marks must equal the final awarded marks.",
        )

    return [item.model_dump() for item in rubric_scores]


def _record_mark_revision(
    db: Session,
    answer: Answer,
    new_marks: float,
    new_feedback: str | None,
    revised_by: int,
):
    """Record mark changes while allowing three total evaluations per answer."""

    if answer.awarded_marks is None:
        return 0

    revision_count = db.query(AnswerMarkRevision).filter(
        AnswerMarkRevision.answer_id == answer.id
    ).count()
    if revision_count >= 2:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The three allowed evaluations for this answer have been used.",
        )

    db.add(AnswerMarkRevision(
        answer_id=answer.id,
        revision_number=revision_count + 1,
        previous_marks=float(answer.awarded_marks),
        new_marks=float(new_marks),
        previous_feedback=answer.examiner_feedback,
        new_feedback=new_feedback,
        revised_by=revised_by,
    ))
    db.add(AdminActivityLog(
        actor_user_id=revised_by,
        action="answer_mark_revised",
        details={
            "answer_id": answer.id,
            "revision_number": revision_count + 1,
            "previous_marks": float(answer.awarded_marks),
            "new_marks": float(new_marks),
        },
    ))
    return revision_count + 1


def _get_submitted_answer_context(
    answer_id: int,
    current_user: User,
    db: Session,
    allow_read_only_admin: bool = False,
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

    if allow_read_only_admin:
        exam = get_visible_exam(session.exam_id, current_user, db)
    else:
        exam = get_authorized_exam(session.exam_id, current_user, db)

    if session.status not in {"submitted", "auto_submitted"}:
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
        Result,
    ).join(
        ExamSession,
        Answer.session_id == ExamSession.id,
    ).join(
        QuestionBank,
        Answer.question_id == QuestionBank.id,
    ).join(
        Exam,
        ExamSession.exam_id == Exam.id,
    ).outerjoin(
        Result,
        Result.session_id == ExamSession.id,
    ).filter(
        ExamSession.status.in_(("submitted", "auto_submitted")),
        QuestionBank.question_type.in_([
            "short_answer",
            "long_answer",
            "image_upload",
        ]),
        Answer.awarded_marks.is_(None),
    )

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
                "difficulty": question.difficulty,
                "expected_answer": question.expected_answer,
                "model_answer_text": question.model_answer_text,
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
                "result_published": bool(result and result.is_published),
                "ai_suggested_marks": answer.ai_suggested_marks,
                "ai_justification": answer.ai_justification,
                "ai_matched_points": answer.ai_matched_points or [],
                "ai_missed_points": answer.ai_missed_points or [],
                "ai_model": answer.ai_model,
                "examiner_feedback": answer.examiner_feedback,
                "image_annotations": answer.image_annotations or [],
                "rubric_scores": answer.rubric_scores or [],
                "ai_suggestion_generated_at": answer.ai_suggestion_generated_at,
                "submitted_at": session.submitted_at,
                "face_photo_url": f"/grading/sessions/{session.id}/face-photo" if session.face_capture_data else None,
            }
            for answer, session, question, exam, result in rows
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

    exam = get_visible_exam(
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
        ExamSession.status.in_(("submitted", "auto_submitted")),
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
                "examiner_feedback": answer.examiner_feedback,
                "image_annotations": answer.image_annotations or [],
                "rubric_scores": answer.rubric_scores or [],
                "submitted_at": session.submitted_at,
                "face_photo_url": f"/grading/sessions/{session.id}/face-photo" if session.face_capture_data else None,
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
        allow_read_only_admin=True,
    )

    if not answer.image_path:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No image is attached to this answer.",
        )

    if answer.image_data:
        image_bytes = (
            answer.thumbnail_data
            if thumbnail and answer.thumbnail_data
            else answer.image_data
        )
        media_type = (
            "image/webp"
            if thumbnail and answer.thumbnail_data
            else answer.image_mime_type or "application/octet-stream"
        )
        return Response(
            content=image_bytes,
            media_type=media_type,
            headers={"Cache-Control": "private, no-store"},
        )

    if answer.image_path.startswith("neon:"):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Stored answer image data is unavailable.",
        )

    # Backward compatibility for answer images saved on the old local filesystem.
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
    }:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Stored answer image has an unsupported format.",
        )

    return FileResponse(path=image_file, media_type=media_type)



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

    if session.status not in {"submitted", "auto_submitted"}:
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

        revision_number = _record_mark_revision(
            db,
            locked_answer,
            submission.awarded_marks,
            submission.examiner_feedback,
            current_user.id,
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
        locked_answer.rubric_scores = _validate_rubric_scores(
            question,
            submission.rubric_scores,
            submission.awarded_marks,
        )
        db.add(AdminActivityLog(
            actor_user_id=current_user.id,
            action="subjective_answer_marked",
            details={
                "answer_id": answer_id,
                "exam_id": exam.id,
                "question_id": question.id,
                "revision_number": revision_number,
                "awarded_marks": float(submission.awarded_marks),
            },
        ))
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


@router.get("/sessions/{session_id}/review")
def get_session_answer_review(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a student's complete paper in the exact delivered question order."""
    require_examiner_or_admin(current_user)
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Exam session not found.")
    exam = get_visible_exam(session.exam_id, current_user, db)
    student = db.query(User).filter(User.id == session.student_id).first()
    result = db.query(Result).filter(Result.session_id == session.id).first()

    ordered_ids = list(session.selected_question_ids or [])
    if not ordered_ids:
        ordered_ids = [
            row[0] for row in db.query(ExamQuestion.question_id).filter(
                ExamQuestion.exam_id == exam.id
            ).order_by(ExamQuestion.question_order.asc(), ExamQuestion.id.asc()).all()
        ]
    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(ordered_ids or [-1])
    ).all()
    question_by_id = {question.id: question for question in questions}
    answers = db.query(Answer).filter(Answer.session_id == session.id).all()
    answer_by_question = {answer.question_id: answer for answer in answers}

    review_items = []
    for order, question_id in enumerate(ordered_ids, start=1):
        question = question_by_id.get(question_id)
        if question is None:
            continue
        answer = answer_by_question.get(question_id)
        revisions = []
        if answer is not None:
            revisions = db.query(AnswerMarkRevision).filter(
                AnswerMarkRevision.answer_id == answer.id
            ).order_by(AnswerMarkRevision.revision_number.asc()).all()
        current_marks = answer.awarded_marks if answer is not None else None
        evaluation_count = (1 + len(revisions)) if current_marks is not None else 0
        question_type_value = getattr(question.question_type, "value", question.question_type)
        selected_options = []
        if answer is not None and question_type_value in {"MCQ", "multi_select"}:
            try:
                selected_option_ids = json.loads(answer.answer_text or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                selected_option_ids = []
            if isinstance(selected_option_ids, int):
                selected_option_ids = [selected_option_ids]
            if isinstance(selected_option_ids, list):
                option_by_id = {option.id: option for option in question.options}
                selected_options = [
                    option_by_id[option_id].option_text
                    for option_id in selected_option_ids
                    if option_id in option_by_id
                ]
        review_items.append({
            "question_id": question.id,
            "question_order": order,
            "question_text": question.question_text,
            "question_image_url": f"/questions/{question.id}/image" if question.question_image_data or question.question_image_path else None,
            "expected_answer_image_url": f"/questions/{question.id}/expected-answer-image" if question.expected_answer_image_data else None,
            "question_type": question_type_value,
            "difficulty": question.difficulty,
            "maximum_marks": question.marks,
            "expected_answer": question.expected_answer,
            "model_answer_text": question.model_answer_text,
            "options": [
                {"id": option.id, "option_text": option.option_text, "is_correct": bool(option.is_correct)}
                for option in question.options
            ],
            "answer_id": answer.id if answer is not None else None,
            "answer_text": answer.answer_text if answer is not None else None,
            "selected_options": selected_options,
            "answer_image_url": f"/grading/answers/{answer.id}/image" if answer is not None and (answer.image_data or answer.image_path) else None,
            "ai_suggested_marks": answer.ai_suggested_marks if answer is not None else None,
            "ai_justification": answer.ai_justification if answer is not None else None,
            "awarded_marks": current_marks,
            "evaluation_count": min(evaluation_count, 3),
            "evaluation_history": [
                {
                    "evaluation_number": 1,
                    "marks": revisions[0].previous_marks,
                    "created_at": revisions[0].created_at,
                }
            ] + [
                {
                    "evaluation_number": revision.revision_number + 1,
                    "marks": revision.new_marks,
                    "created_at": revision.created_at,
                }
                for revision in revisions
            ] if revisions else (
                [{"evaluation_number": 1, "marks": current_marks, "created_at": None}]
                if answer is not None and current_marks is not None else []
            ),
            "examiner_feedback": answer.examiner_feedback if answer is not None else None,
            "is_objective": getattr(question.question_type, "value", question.question_type) in {"MCQ", "multi_select"},
        })

    return {
        "session_id": session.id,
        "exam_id": exam.id,
        "exam_title": exam.title,
        "student_id": student.id if student else session.student_id,
        "student_name": student.full_name if student else "Unknown student",
        "department": student.department if student else None,
        "session_status": session.status,
        "started_at": session.started_at,
        "submitted_at": session.submitted_at,
        "face_photo_url": f"/grading/sessions/{session.id}/face-photo" if session.face_capture_data else None,
        "result_published": bool(result and result.is_published),
        "result_obtained_marks": result.obtained_marks if result else None,
        "result_total_marks": result.total_marks if result else None,
        "result_grade": (result.grade or ("A+" if float(result.percentage or 0) >= 90 else "A" if float(result.percentage or 0) >= 80 else "B" if float(result.percentage or 0) >= 70 else "C" if float(result.percentage or 0) >= 60 else "D" if float(result.percentage or 0) >= 50 else "F")) if result and result.is_published else None,
        "questions": review_items,
    }


@router.get("/sessions")
def list_submitted_sessions_for_review(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List candidate progress and submitted sessions visible to this examiner or Admin."""
    require_examiner_or_admin(current_user)

    query = db.query(
        ExamSession,
        Exam,
        User,
        Result,
    ).join(
        Exam,
        ExamSession.exam_id == Exam.id,
    ).join(
        User,
        ExamSession.student_id == User.id,
    ).outerjoin(
        Result,
        Result.session_id == ExamSession.id,
    ).filter(
        ExamSession.status.in_(("not_started", "in_progress", "submitted", "auto_submitted")),
    )

    role = getattr(current_user.role, "value", current_user.role)
    if role == "examiner":
        query = query.filter(Exam.created_by == current_user.id)

    rows = query.order_by(
        ExamSession.submitted_at.desc(),
        ExamSession.id.desc(),
    ).all()

    return {
        "sessions": [
            {
                "session_id": session.id,
                "exam_id": exam.id,
                "exam_title": exam.title,
                "student_id": student.id,
                "student_name": student.full_name,
                "session_status": session.status,
                "can_manage": exam.created_by == current_user.id,
                "submitted_at": session.submitted_at,
                "face_photo_url": f"/grading/sessions/{session.id}/face-photo" if session.face_capture_data else None,
                "result_ready": result is not None,
                "is_published": bool(result.is_published) if result else False,
                "obtained_marks": result.obtained_marks if result else None,
                "total_marks": result.total_marks if result else None,
                "percentage": result.percentage if result else None,
            }
            for session, exam, student, result in rows
        ]
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

    if session.status not in {"submitted", "auto_submitted"}:
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

            _record_mark_revision(
                db,
                answer,
                item.awarded_marks,
                item.examiner_feedback,
                current_user.id,
            )
            answer.awarded_marks = float(item.awarded_marks)
            answer.examiner_feedback = item.examiner_feedback
            answer.image_annotations = (
                [annotation.model_dump() for annotation in item.image_annotations]
                if item.image_annotations
                else None
            )
            answer.rubric_scores = _validate_rubric_scores(
                question,
                item.rubric_scores,
                item.awarded_marks,
            )

        db.add(AdminActivityLog(
            actor_user_id=current_user.id,
            action="subjective_answers_bulk_graded",
            details={
                "session_id": session_id,
                "answer_ids": answer_ids,
            },
        ))
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
    submission: PublishResultRequest = Body(default=PublishResultRequest()),
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

    if session.status not in {"submitted", "auto_submitted"}:
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
        custom_grade = (submission.grade or "").strip()
        result.grade = custom_grade or None
        result.is_published = True
        result.published_at = datetime.utcnow()
        db.add(AdminActivityLog(
            actor_user_id=current_user.id,
            action="examination_result_published",
            details={
                "session_id": session_id,
                "exam_id": session.exam_id,
                "result_id": result.id,
            },
        ))
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

    locked_answer = db.query(Answer).filter(
        Answer.id == answer_id,
    ).with_for_update().first()
    if locked_answer is None:
        raise HTTPException(status_code=404, detail="Answer not found.")

    revision_number = _record_mark_revision(
        db,
        locked_answer,
        submission.awarded_marks,
        submission.examiner_feedback,
        current_user.id,
    )
    approval = approve_subjective_marks(
        db=db,
        answer_id=answer_id,
        awarded_marks=submission.awarded_marks,
        current_user=current_user,
    )
    locked_answer.examiner_feedback = submission.examiner_feedback
    locked_answer.image_annotations = (
        [annotation.model_dump() for annotation in submission.image_annotations]
        if submission.image_annotations else None
    )
    locked_answer.rubric_scores = _validate_rubric_scores(
        question,
        submission.rubric_scores,
        submission.awarded_marks,
    )
    db.add(AdminActivityLog(
        actor_user_id=current_user.id,
        action="ai_suggested_marks_human_approved",
        details={
            "answer_id": answer_id,
            "exam_id": exam.id,
            "approved_marks": float(submission.awarded_marks),
            "revision_number": revision_number,
        },
    ))
    db.commit()

    result = calculate_session_result(
        db,
        session.id,
    )

    return {
        **approval,
        "result": result,
        "result_ready": result.get("status") == "evaluated",
    }


@router.get("/answers/{answer_id}/mark-revisions")
def get_answer_mark_revisions(
    answer_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current final mark and its human revision audit trail."""
    require_examiner_or_admin(current_user)
    answer, session, exam, question = _get_submitted_answer_context(
        answer_id,
        current_user,
        db,
        allow_read_only_admin=True,
    )
    revisions = db.query(AnswerMarkRevision).filter(
        AnswerMarkRevision.answer_id == answer_id
    ).order_by(AnswerMarkRevision.revision_number.asc()).all()
    return {
        "answer_id": answer.id,
        "exam_id": exam.id,
        "question_id": question.id,
        "maximum_marks": question.marks,
        "current_final_marks": answer.awarded_marks,
        "revision_limit": 2,
        "evaluation_limit": 3,
        "revisions_used": len(revisions),
        "evaluation_count": (1 + len(revisions)) if answer.awarded_marks is not None else 0,
        "revisions_remaining": max(0, 3 - ((1 + len(revisions)) if answer.awarded_marks is not None else 0)),
        "history": [
            {
                "revision_number": item.revision_number,
                "previous_marks": item.previous_marks,
                "new_marks": item.new_marks,
                "previous_feedback": item.previous_feedback,
                "new_feedback": item.new_feedback,
                "revised_by": item.revised_by,
                "created_at": item.created_at,
            }
            for item in revisions
        ],
    }


@router.get("/graded")
def get_previously_graded_subjective_answers(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List previously graded subjective answers so staff can use allowed revisions."""
    require_examiner_or_admin(current_user)
    query = db.query(
        Answer, ExamSession, QuestionBank, Exam, User, Result
    ).join(
        ExamSession, Answer.session_id == ExamSession.id
    ).join(
        QuestionBank, Answer.question_id == QuestionBank.id
    ).join(
        Exam, Exam.id == ExamSession.exam_id
    ).join(
        User, User.id == ExamSession.student_id
    ).outerjoin(
        Result, Result.session_id == ExamSession.id
    ).filter(
        ExamSession.status.in_(("submitted", "auto_submitted")),
        QuestionBank.question_type.in_(["short_answer", "long_answer", "image_upload"]),
        Answer.awarded_marks.isnot(None),
    )
    query = query.filter(Exam.created_by == current_user.id)

    rows = query.order_by(
        ExamSession.submitted_at.desc(),
        Answer.id.desc(),
    ).limit(1000).all()

    return {
        "total_graded": len(rows),
        "answers": [
            {
                "answer_id": answer.id,
                "session_id": session.id,
                "student_id": student.id,
                "student_name": student.full_name,
                "exam_id": exam.id,
                "exam_title": exam.title,
                "question_id": question.id,
                "question_text": question.question_text,
                "question_type": getattr(question.question_type, "value", question.question_type),
                "difficulty": question.difficulty,
                "expected_answer": question.expected_answer,
                "model_answer_text": question.model_answer_text,
                "answer_text": answer.answer_text,
                "image_path": answer.image_path,
                "marks": question.marks,
                "awarded_marks": answer.awarded_marks,
                "ai_suggested_marks": answer.ai_suggested_marks,
                "ai_justification": answer.ai_justification,
                "ai_matched_points": answer.ai_matched_points or [],
                "ai_missed_points": answer.ai_missed_points or [],
                "ai_model": answer.ai_model,
                "examiner_feedback": answer.examiner_feedback,
                "image_annotations": answer.image_annotations or [],
                "rubric_scores": answer.rubric_scores or [],
                "submitted_at": session.submitted_at,
                "face_photo_url": f"/grading/sessions/{session.id}/face-photo" if session.face_capture_data else None,
            }
            for answer, session, question, exam, student, result in rows
        ],
    }
