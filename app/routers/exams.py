
from datetime import timezone

from fastapi import APIRouter, Body, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Exam, ExamQuestion, ExamSession, QuestionBank, Option
from app.schemas import ExamCreate, QuestionCreate, UserRole
from app.services.question_validation import validate_question
from app.dependencies import require_role
from app.services.exam_config import (
    validate_exam_config,
    normalize_to_naive_utc,
)


router = APIRouter(
    prefix="/exams",
    tags=["Exam Configuration"]
)


# ==========================================
# CREATE EXAM
# ==========================================

@router.post("/", status_code=status.HTTP_201_CREATED)
def create_exam(
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("examiner", "admin")
    )
):
    try:
        validate_exam_config(
            data.duration_minutes,
            data.start_time,
            data.end_time,
            data.selection_rules,
            data.total_questions,
            data.gaze_tracking_sensitivity,
            data.max_tab_switch_warnings,
        )

    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error)
        )

    exam = Exam(
        title=data.title,
        subject=data.subject,
        duration_minutes=data.duration_minutes,
        total_questions=data.total_questions,
        randomize_questions=data.randomize_questions,
        selection_rules=data.selection_rules,

        start_time=normalize_to_naive_utc(
            data.start_time
        ),

        end_time=normalize_to_naive_utc(
            data.end_time
        ),

        negative_marking=data.negative_marking,
        proctoring_enabled=data.proctoring_enabled,
        gaze_tracking_sensitivity=data.gaze_tracking_sensitivity,
        max_tab_switch_warnings=data.max_tab_switch_warnings,
        created_by=current_user.id,
    )

    try:
        db.add(exam)
        db.commit()
        db.refresh(exam)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Exam could not be created because of a database constraint."
        )

    return {
        "message": "Exam created successfully",
        "exam_id": exam.id,
    }


# ==========================================
# LIST EXAMS
# ==========================================

@router.get("/")
def list_exams(
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("student", "examiner", "admin")
    )
):
    query = db.query(Exam)

    # Students can discover available examinations.
    # Examiners can access only their own exams.
    # Admins can view all exams.
    if current_user.role == UserRole.EXAMINER.value:
        query = query.filter(
            Exam.created_by == current_user.id
        )

    exams = query.order_by(
        Exam.id.desc()
    ).all()

    def utc_timestamp(value):
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    return [
        {
            "id": exam.id,
            "title": exam.title,
            "subject": exam.subject,
            "duration_minutes": exam.duration_minutes,
            "total_questions": exam.total_questions,
            "randomize_questions": exam.randomize_questions,
            "selection_rules": exam.selection_rules,
            "start_time": utc_timestamp(exam.start_time),
            "end_time": utc_timestamp(exam.end_time),
            "negative_marking": exam.negative_marking,
            "proctoring_enabled": exam.proctoring_enabled,
            "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
            "max_tab_switch_warnings": exam.max_tab_switch_warnings,
            "created_by": exam.created_by,
        }
        for exam in exams
    ]
    



# ==========================================
# ADD A QUESTION TO AN EXAMINATION BANK
# ==========================================

@router.post("/{exam_id}/questions", status_code=status.HTTP_201_CREATED)
def add_exam_question(
    exam_id: int,
    data: QuestionCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Create a question owned by this exam's creator and add it to its bank."""

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )
    if exam.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the examination creator can add questions.",
        )
    if db.query(ExamSession.id).filter(
        ExamSession.exam_id == exam_id
    ).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Questions cannot be added after an exam session has been created.",
        )
    if exam.subject and data.subject.casefold() != exam.subject.casefold():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The question subject must match the examination subject.",
        )

    question_type = getattr(data.question_type, "value", data.question_type)
    options = data.options or []
    try:
        validate_question(
            question_type,
            data.question_text,
            data.marks,
            options,
            data.negative_marks,
            data.correct_option_index,
            data.correct_option_indices,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(error),
        )

    # All questions of the same type and difficulty in an exam share
    # one maximum-mark value.
    existing_group = db.query(QuestionBank).join(
        ExamQuestion,
        ExamQuestion.question_id == QuestionBank.id,
    ).filter(
        ExamQuestion.exam_id == exam_id,
        QuestionBank.question_type == question_type,
        QuestionBank.difficulty == data.difficulty.value,
    ).first()
    if existing_group and float(existing_group.marks or 0) != float(data.marks):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Maximum marks must be equal for the same question type and difficulty.",
        )

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
        created_by=current_user.id,
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
            db.add(Option(
                question_id=question.id,
                option_text=option_text,
                is_correct=is_correct,
            ))
        db.add(ExamQuestion(
            exam_id=exam_id,
            question_id=question.id,
            question_order=(
                db.query(ExamQuestion)
                .filter(ExamQuestion.exam_id == exam_id)
                .count() + 1
            ),
        ))
        db.commit()
        db.refresh(question)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The question could not be added to this examination bank.",
        )

    return {
        "message": "Question added to the examination question bank.",
        "exam_id": exam_id,
        "question_id": question.id,
    }


# ==========================================
# REMOVE A QUESTION FROM AN EXAMINATION BANK
# ==========================================

@router.delete("/{exam_id}/questions/{question_id}")
def remove_exam_question(
    exam_id: int,
    question_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Remove only this exam's link; keep the original question intact."""

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )
    if exam.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the examination creator can remove questions.",
        )
    if db.query(ExamSession.id).filter(
        ExamSession.exam_id == exam_id
    ).first() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Questions cannot be removed after an exam session has been created.",
        )

    assignment = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam_id,
        ExamQuestion.question_id == question_id,
    ).first()
    if assignment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question is not part of this examination bank.",
        )

    remaining = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam_id,
        ExamQuestion.id != assignment.id,
    ).count()
    if remaining < (exam.total_questions or 0):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Removing this question would leave fewer questions than the examination requires.",
        )

    db.delete(assignment)
    db.commit()
    return {
        "message": "Question removed from this examination bank. The original question was preserved.",
        "exam_id": exam_id,
        "question_id": question_id,
    }


# ==========================================
# ASSIGN QUESTIONS TO AN EXAM
# ==========================================

@router.put("/{exam_id}/questions")
def assign_exam_questions(
    exam_id: int,
    question_ids: list[int] = Body(..., min_length=1),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Replace an exam's question assignments before any student starts."""

    exam = db.query(Exam).filter(
        Exam.id == exam_id,
    ).first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    # Ownership applies equally to Admins and Examiners. Admins may
    # inspect every examination, but must not edit another creator's exam.
    if exam.created_by != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the examination creator can change its question assignments.",
        )

    if any(
        isinstance(question_id, bool)
        or not isinstance(question_id, int)
        or question_id <= 0
        for question_id in question_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question IDs must be positive integers.",
        )

    if len(question_ids) != len(set(question_ids)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate question IDs are not allowed.",
        )

    if len(question_ids) < exam.total_questions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Assigned questions cannot be fewer than the exam question count.",
        )

    existing_sessions = db.query(ExamSession.id).filter(
        ExamSession.exam_id == exam_id,
    ).first()

    if existing_sessions is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question assignments cannot change after an exam session has been created.",
        )

    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(question_ids),
    ).all()

    if len(questions) != len(question_ids):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="One or more question IDs do not exist.",
        )

    if exam.subject:
        mismatched = [
            question.id
            for question in questions
            if question.subject.casefold() != exam.subject.casefold()
        ]
        if mismatched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Every assigned question must match the exam subject.",
        )

    try:
        db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == exam_id,
        ).delete(synchronize_session=False)

        for order, question_id in enumerate(question_ids, start=1):
            db.add(
                ExamQuestion(
                    exam_id=exam_id,
                    question_id=question_id,
                    question_order=order,
                )
            )

        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Question assignments could not be saved.",
        )

    return {
        "message": "Exam questions assigned successfully.",
        "exam_id": exam_id,
        "assigned_question_ids": question_ids,
        "total_assigned": len(question_ids),
    }


@router.get("/{exam_id}/questions")
def list_exam_questions(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """List assigned questions in their configured order."""

    exam = db.query(Exam).filter(
        Exam.id == exam_id,
    ).first()

    if exam is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam not found.",
        )

    if (
        current_user.role == UserRole.EXAMINER.value
        and exam.created_by != current_user.id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view assignments for your own examinations.",
        )

    assignments = db.query(
        ExamQuestion,
        QuestionBank,
    ).join(
        QuestionBank,
        QuestionBank.id == ExamQuestion.question_id,
    ).filter(
        ExamQuestion.exam_id == exam_id,
    ).order_by(
        ExamQuestion.question_order.asc(),
        ExamQuestion.id.asc(),
    ).all()

    return {
        "exam_id": exam_id,
        "total_assigned": len(assignments),
        "questions": [
            {
                "question_id": question.id,
                "question_order": assignment.question_order,
                "question_text": question.question_text,
                "question_type": getattr(
                    question.question_type,
                    "value",
                    question.question_type,
                ),
                "subject": question.subject,
                "difficulty": question.difficulty,
                "marks": question.marks,
            }
            for assignment, question in assignments
        ],
    }
