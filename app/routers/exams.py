
from datetime import datetime, timezone
import math

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.question_bank_models import QuestionCollectionItem
from app.models import (
    AdminActivityLog, Exam, ExamQuestion, ExamSession, QuestionBank, Option, Answer,
    AnswerMarkRevision, Result, ProctorEvent, ExamAssignment, ExamConfigurationRevision, ExamQuestionMarksRevision, User,
)
from app.schemas import ExamCreate, ExamScheduleUpdate, QuestionCreate, UserRole
from app.services.question_validation import validate_question
from app.dependencies import require_role
from app.services.session_service import generate_session_question_ids
from app.services.exam_config import (
    validate_exam_config,
    normalize_to_naive_utc,
    normalize_schedule_input_to_naive_utc,
)


router = APIRouter(
    prefix="/exams",
    tags=["Exam Configuration"]
)

def _audit_exam_action(db: Session, actor_id: int, action: str, details: dict):
    """Record examination-management actions for platform audit history."""
    db.add(AdminActivityLog(
        actor_user_id=actor_id,
        action=action,
        details=details,
    ))


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

        start_time=normalize_schedule_input_to_naive_utc(
            data.start_time
        ),

        end_time=normalize_schedule_input_to_naive_utc(
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
        db.flush()
        db.add(ExamConfigurationRevision(
            exam_id=exam.id,
            revision_number=0,
            configuration_snapshot={
                "title": exam.title,
                "subject": exam.subject,
                "duration_minutes": exam.duration_minutes,
                "total_questions": exam.total_questions,
                "randomize_questions": exam.randomize_questions,
                "selection_rules": exam.selection_rules,
                "start_time": normalize_schedule_input_to_naive_utc(data.start_time).replace(tzinfo=timezone.utc).isoformat() if exam.start_time else None,
                "end_time": normalize_schedule_input_to_naive_utc(data.end_time).replace(tzinfo=timezone.utc).isoformat() if exam.end_time else None,
                "negative_marking": exam.negative_marking,
                "proctoring_enabled": exam.proctoring_enabled,
                "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
                "max_tab_switch_warnings": exam.max_tab_switch_warnings,
            },
            changed_by=current_user.id,
        ))
        _audit_exam_action(db, current_user.id, "examination_created", {
            "exam_id": exam.id,
            "title": exam.title,
        })
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
    mine: bool = False,
    db: Session = Depends(get_db),
    current_user=Depends(
        require_role("student", "examiner", "admin")
    )
):
    query = db.query(Exam)

    # The Manage Examination page asks for only the current user's exams.
    # The normal examination list still lets Admins view every exam.
    if mine:
        if current_user.role == UserRole.STUDENT.value:
            raise HTTPException(status_code=403, detail="Only Admins and Examiners can manage examinations.")
        query = query.filter(Exam.created_by == current_user.id)
    # Students can discover available examinations.
    # Examiners can access only their own exams.
    # Admins can view all exams.
    elif current_user.role == UserRole.EXAMINER.value:
        query = query.filter(Exam.created_by == current_user.id)
    elif current_user.role == UserRole.STUDENT.value:
        query = query.join(
            ExamAssignment,
            ExamAssignment.exam_id == Exam.id,
        ).filter(
            ExamAssignment.student_id == current_user.id,
            ExamAssignment.is_active.is_(True),
        )

    exams = query.order_by(
        Exam.id.desc()
    ).all()

    creator_ids = {exam.created_by for exam in exams}
    creators = db.query(User).filter(User.id.in_(creator_ids)).all() if creator_ids else []
    creator_names = {
        creator.id: creator.full_name
        for creator in creators
    }
    creator_roles = {
        creator.id: creator.role
        for creator in creators
    }

    def utc_timestamp(value):
        if value is None:
            return None

        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)

        return value.astimezone(timezone.utc)

    # Calculate the maximum marks using the selected question groups.
    # If the selected paper cannot be calculated safely, return no value
    # rather than showing an incorrect total.
    max_marks_by_exam = {}
    for exam in exams:
        assigned_questions = db.query(
            QuestionBank.question_type,
            QuestionBank.difficulty,
            QuestionBank.marks,
        ).join(
            ExamQuestion,
            ExamQuestion.question_id == QuestionBank.id,
        ).filter(
            ExamQuestion.exam_id == exam.id,
        ).all()

        marks_by_group = {}
        for question_type, difficulty, marks in assigned_questions:
            question_type = getattr(question_type, "value", question_type)
            marks_by_group[(difficulty, question_type)] = float(marks or 0)

        selection_rules = exam.selection_rules or {}
        group_counts = selection_rules.get("group_counts") if isinstance(selection_rules, dict) else None
        maximum = None

        if isinstance(group_counts, dict):
            needed_groups = [
                (key.split("|", 1)[0], key.split("|", 1)[1], int(count))
                for key, count in group_counts.items()
                if int(count) > 0 and "|" in key
            ]
            if all((difficulty, question_type) in marks_by_group for difficulty, question_type, _ in needed_groups):
                maximum = sum(
                    marks_by_group[(difficulty, question_type)] * count
                    for difficulty, question_type, count in needed_groups
                )
        elif len(assigned_questions) == int(exam.total_questions or 0):
            maximum = sum(float(row[2] or 0) for row in assigned_questions)
        elif assigned_questions:
            available_marks = {float(row[2] or 0) for row in assigned_questions}
            if len(available_marks) == 1:
                maximum = next(iter(available_marks)) * int(exam.total_questions or 0)

        max_marks_by_exam[exam.id] = round(maximum, 2) if maximum is not None else None

    return [
        {
            "id": exam.id,
            "title": exam.title,
            "subject": exam.subject,
            "duration_minutes": exam.duration_minutes,
            "total_questions": exam.total_questions,
            "max_marks": max_marks_by_exam.get(exam.id),
            "randomize_questions": exam.randomize_questions,
            "selection_rules": exam.selection_rules,
            "start_time": utc_timestamp(exam.start_time),
            "end_time": utc_timestamp(exam.end_time),
            "negative_marking": exam.negative_marking,
            "proctoring_enabled": exam.proctoring_enabled,
            "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
            "max_tab_switch_warnings": exam.max_tab_switch_warnings,
            "created_by": exam.created_by,
            "created_by_name": creator_names.get(exam.created_by, "Unknown"),
            "created_by_role": creator_roles.get(exam.created_by),
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
        last_assignment = db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == exam_id
        ).order_by(
            ExamQuestion.question_order.desc(),
            ExamQuestion.id.desc(),
        ).first()
        next_order = (last_assignment.question_order or 0) + 1 if last_assignment else 1
        db.add(ExamQuestion(
            exam_id=exam_id,
            question_id=question.id,
            question_order=next_order,
        ))
        _audit_exam_action(db, current_user.id, "exam_question_added", {
            "exam_id": exam_id,
            "question_id": question.id,
        })
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

    db.delete(assignment)
    _audit_exam_action(db, current_user.id, "exam_question_removed_from_bank", {
        "exam_id": exam_id,
        "question_id": question_id,
    })
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

    current_bank_ids = {
        row[0] for row in db.query(ExamQuestion.question_id).filter(
            ExamQuestion.exam_id == exam_id
        ).all()
    }
    if not set(question_ids).issubset(current_bank_ids):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only questions already copied into this examination bank can be assigned. Use the previous-bank reuse endpoint to create independent copies first.",
        )

    if exam.subject:
        mismatched = [
            question.id
            for question in questions
            if (question.subject or "").casefold() != exam.subject.casefold()
        ]
        if mismatched:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Every assigned question must match the exam subject.",
            )

    marks_by_group = {}
    for question in questions:
        question_type = getattr(question.question_type, "value", question.question_type)
        group = (question_type, question.difficulty)
        configured_marks = float(question.marks or 0)
        if group in marks_by_group and not math.isclose(
            marks_by_group[group], configured_marks, rel_tol=0, abs_tol=0.0001
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum marks must be equal within each question type and difficulty group.",
            )
        marks_by_group[group] = configured_marks

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
        "created_by": exam.created_by,
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
                "tags": question.tags or [],
                "question_time_limit_seconds": assignment.question_time_limit_seconds,
                "source_question_id": question.source_question_id,
                "expected_answer": question.expected_answer,
                "model_answer_text": question.model_answer_text,
                "options": [
                    {
                        "id": option.id,
                        "option_text": option.option_text,
                        "is_correct": bool(option.is_correct),
                    }
                    for option in question.options
                ],
                "question_image_available": bool(
                    question.question_image_path or question.question_image_data
                ),
            }
            for assignment, question in assignments
        ],
    }


# ==========================================
# QUESTION BANK AND EXAM WORKFLOW REQUESTS
# ==========================================

class ReuseQuestionsRequest(BaseModel):
    question_ids: list[int] = Field(min_length=1, max_length=500)


class AssignStudentsRequest(BaseModel):
    student_ids: list[int] = Field(min_length=1, max_length=2000)


class QuestionTimerRequest(BaseModel):
    seconds: int | None = Field(default=None, ge=1, le=7200)


# ==========================================
# LIST PREVIOUS QUESTION BANKS AVAILABLE FOR REUSE
# ==========================================

@router.get("/{exam_id}/question-bank/sources")
def list_reusable_question_banks(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """List completed/previous exam banks the current creator may reuse."""

    target = db.query(Exam).filter(Exam.id == exam_id).first()
    if target is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if target.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can manage this question bank.")

    query = db.query(Exam, ExamQuestion, QuestionBank).join(
        ExamQuestion, ExamQuestion.exam_id == Exam.id
    ).join(
        QuestionBank, QuestionBank.id == ExamQuestion.question_id
    ).filter(
        Exam.id < target.id,
        Exam.created_by == current_user.id,
    )
    if current_user.role == UserRole.ADMIN.value:
        query = db.query(Exam, ExamQuestion, QuestionBank).join(
            ExamQuestion, ExamQuestion.exam_id == Exam.id
        ).join(
            QuestionBank, QuestionBank.id == ExamQuestion.question_id
        ).filter(Exam.id < target.id)

    rows = query.order_by(Exam.id.desc(), ExamQuestion.question_order.asc()).all()
    banks = {}
    for source_exam, assignment, question in rows:
        if target.subject and (question.subject or "").casefold() != target.subject.casefold():
            continue
        bank = banks.setdefault(source_exam.id, {
            "source_exam_id": source_exam.id,
            "source_exam_title": source_exam.title,
            "subject": source_exam.subject,
            "questions": [],
        })
        bank["questions"].append({
            "question_id": question.id,
            "question_text": question.question_text,
            "question_type": getattr(question.question_type, "value", question.question_type),
            "difficulty": question.difficulty,
            "marks": question.marks,
            "source_question_id": question.source_question_id,
        })
    return {"exam_id": exam_id, "banks": list(banks.values())}


# ==========================================
# COPY QUESTIONS INTO THE NEW EXAMINATION BANK
# ==========================================

@router.post("/{exam_id}/question-bank/reuse", status_code=status.HTTP_201_CREATED)
def reuse_questions_from_previous_banks(
    exam_id: int,
    data: ReuseQuestionsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Copy selected previous-bank questions as independent exam snapshots."""

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can add questions.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id).first():
        raise HTTPException(status_code=409, detail="The question bank is locked after an exam session is created.")
    if len(data.question_ids) != len(set(data.question_ids)):
        raise HTTPException(status_code=400, detail="Duplicate question IDs are not allowed.")

    source_rows = db.query(QuestionBank).filter(
        QuestionBank.id.in_(data.question_ids)
    ).all()
    if len(source_rows) != len(data.question_ids):
        raise HTTPException(status_code=404, detail="One or more source questions do not exist.")

    already_reused = {
        row[0] for row in db.query(QuestionBank.source_question_id).join(
            ExamQuestion, ExamQuestion.question_id == QuestionBank.id
        ).filter(
            ExamQuestion.exam_id == exam_id,
            QuestionBank.source_question_id.isnot(None),
        ).all()
    }
    if set(data.question_ids).intersection(already_reused):
        raise HTTPException(
            status_code=409,
            detail="One or more selected source questions are already copied into this examination bank.",
        )

    source_ids = {question.id for question in source_rows}
    source_assignments = db.query(ExamQuestion, Exam).join(
        Exam, Exam.id == ExamQuestion.exam_id
    ).filter(ExamQuestion.question_id.in_(source_ids)).all()
    allowed_source_ids = set()
    for assignment, source_exam in source_assignments:
        if source_exam.id >= exam_id:
            continue
        if current_user.role == UserRole.ADMIN.value or source_exam.created_by == current_user.id:
            allowed_source_ids.add(assignment.question_id)
    if allowed_source_ids != source_ids:
        raise HTTPException(
            status_code=403,
            detail="You may reuse only questions from question banks you are authorized to access.",
        )

    existing_ids = {
        row[0] for row in db.query(ExamQuestion.question_id).filter(
            ExamQuestion.exam_id == exam_id,
            ExamQuestion.question_id.in_(data.question_ids),
        ).all()
    }
    if existing_ids:
        raise HTTPException(status_code=409, detail="One or more questions are already in this examination bank.")

    last_assignment = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam_id
    ).order_by(
        ExamQuestion.question_order.desc(),
        ExamQuestion.id.desc(),
    ).first()
    last_order = (last_assignment.question_order or 0) if last_assignment else 0
    marks_by_group = {}
    existing_groups = db.query(QuestionBank).join(
        ExamQuestion, ExamQuestion.question_id == QuestionBank.id
    ).filter(ExamQuestion.exam_id == exam_id).all()
    for existing in existing_groups:
        group_key = (
            getattr(existing.question_type, "value", existing.question_type),
            existing.difficulty,
        )
        marks_by_group[group_key] = float(existing.marks or 0)

    new_questions = []
    try:
        for source in source_rows:
            if exam.subject and (source.subject or "").casefold() != exam.subject.casefold():
                raise HTTPException(status_code=400, detail="Every reused question must match the examination subject.")

            group_key = (
                getattr(source.question_type, "value", source.question_type),
                source.difficulty,
            )
            # Marks are configured by the creator of the destination exam.
            # Preserve an existing exam-specific value for this group; otherwise
            # use a temporary 1-mark default that the creator can change below.
            exam_marks = marks_by_group.get(group_key, 1.0)
            marks_by_group[group_key] = exam_marks

            copied = QuestionBank(
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
                marks=exam_marks,
                negative_marks=source.negative_marks,
                tags=list(source.tags or []),
                created_by=current_user.id,
                source_question_id=source.id,
            )
            db.add(copied)
            db.flush()
            for option in source.options:
                db.add(Option(
                    question_id=copied.id,
                    option_text=option.option_text,
                    is_correct=option.is_correct,
                ))
            new_questions.append(copied)

        for offset, copied in enumerate(new_questions, start=1):
            db.add(ExamQuestion(
                exam_id=exam_id,
                question_id=copied.id,
                question_order=last_order + offset,
            ))
        _audit_exam_action(db, current_user.id, "exam_questions_reused", {
            "exam_id": exam_id,
            "source_question_ids": data.question_ids,
            "copied_question_ids": [question.id for question in new_questions],
        })
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return {
        "message": "Questions copied into this examination as independent snapshots.",
        "exam_id": exam_id,
        "copied_question_ids": [question.id for question in new_questions],
        "source_question_ids": [question.source_question_id for question in new_questions],
    }


# ==========================================
# DELETE THE COMPLETE EXAMINATION QUESTION BANK
# ==========================================

@router.delete("/{exam_id}/question-bank")
def delete_exam_question_bank(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Delete one exam's bank links without deleting reused/original records."""

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the examination creator can delete this question bank.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id).first():
        raise HTTPException(
            status_code=409,
            detail="A question bank cannot be deleted after an exam session has been created.",
        )

    assignments = db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).all()
    question_ids = [item.question_id for item in assignments]
    for assignment in assignments:
        db.delete(assignment)
    db.flush()

    # Remove only unused, locally-created snapshots. A source question or
    # any question referenced by another exam or answer is always preserved.
    removed_question_ids = []
    for question_id in question_ids:
        question = db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
        if question is None or question.created_by != current_user.id:
            continue
        still_assigned = db.query(ExamQuestion.id).filter(
            ExamQuestion.question_id == question_id
        ).first()
        has_answers = db.query(Answer.id).filter(
            Answer.question_id == question_id
        ).first()
        used_as_source = db.query(QuestionBank.id).filter(
            QuestionBank.source_question_id == question_id
        ).first()
        if still_assigned is None and has_answers is None and used_as_source is None:
            db.delete(question)
            removed_question_ids.append(question_id)

    active_assignments = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.is_active.is_(True),
    ).all()
    for student_assignment in active_assignments:
        student_assignment.is_active = False

    _audit_exam_action(db, current_user.id, "exam_question_bank_deleted", {
        "exam_id": exam_id,
        "removed_bank_entries": len(assignments),
        "removed_question_records": removed_question_ids,
        "deactivated_student_assignments": [
            item.student_id for item in active_assignments
        ],
    })
    db.commit()
    return {
        "message": "The examination question bank was deleted. Shared source questions and questions used by other exams were preserved.",
        "exam_id": exam_id,
        "removed_question_records": removed_question_ids,
        "removed_bank_entries": len(assignments),
    }


# ==========================================
# ASSIGN EXAM TO SELECTED STUDENTS
# ==========================================

@router.post("/{exam_id}/assignments")
def assign_exam_to_students(
    exam_id: int,
    data: AssignStudentsRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can assign students.")
    if len(data.student_ids) != len(set(data.student_ids)):
        raise HTTPException(status_code=400, detail="Duplicate student IDs are not allowed.")

    students = db.query(User).filter(User.id.in_(data.student_ids)).all()
    if len(students) != len(data.student_ids) or any(
        student.role != UserRole.STUDENT.value or not student.is_active
        for student in students
    ):
        raise HTTPException(status_code=400, detail="Every assigned account must be an active Student.")

    try:
        for student in students:
            assignment = db.query(ExamAssignment).filter(
                ExamAssignment.exam_id == exam_id,
                ExamAssignment.student_id == student.id,
            ).first()

            student_session = db.query(ExamSession.id).filter(
                ExamSession.exam_id == exam_id,
                ExamSession.student_id == student.id,
            ).first()

            if assignment is not None and not assignment.is_active and student_session is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"{student.full_name} already has an examination session. Their revoked access cannot be restored.",
                )

            if assignment is None:
                db.add(ExamAssignment(
                    exam_id=exam_id,
                    student_id=student.id,
                    assigned_by=current_user.id,
                    is_active=True,
                ))
            else:
                assignment.is_active = True
                assignment.assigned_by = current_user.id
        _audit_exam_action(db, current_user.id, "exam_assigned_to_students", {
            "exam_id": exam_id,
            "student_ids": data.student_ids,
        })
        db.commit()
    except Exception:
        db.rollback()
        raise

    return {"message": "Examination assigned successfully.", "exam_id": exam_id, "student_ids": data.student_ids}


@router.get("/{exam_id}/assignments")
def list_exam_assignments(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can view its assignments.")
    rows = db.query(ExamAssignment, User).join(
        User, User.id == ExamAssignment.student_id
    ).filter(
        ExamAssignment.exam_id == exam_id,
    ).order_by(User.full_name.asc()).all()

    sessions = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id
    ).all()
    session_status_by_student = {
        session.student_id: session.status
        for session in sessions
    }

    return {
        "exam_id": exam_id,
        "students": [
            {
                "student_id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "assigned_at": assignment.assigned_at,
                "is_active": assignment.is_active,
                "session_status": session_status_by_student.get(user.id),
            }
            for assignment, user in rows
        ],
    }


# ==========================================
# REMOVE A STUDENT FROM AN EXAMINATION
# ==========================================

@router.delete("/{exam_id}/assignments/{student_id}")
def revoke_exam_assignment(
    exam_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Stop a student's access while keeping their account and exam history."""

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")

    if exam.created_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="Only the examination creator can remove student access.",
        )

    assignment = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.student_id == student_id,
    ).first()

    if assignment is None:
        raise HTTPException(
            status_code=404,
            detail="This student is not assigned to the examination.",
        )

    if not assignment.is_active:
        return {
            "message": "This student's examination access has already been removed.",
            "exam_id": exam_id,
            "student_id": student_id,
            "is_active": False,
        }

    assignment.is_active = False
    _audit_exam_action(db, current_user.id, "exam_student_access_revoked", {
        "exam_id": exam_id,
        "student_id": student_id,
    })
    db.commit()

    return {
        "message": "Student access removed. Their account and examination history were kept.",
        "exam_id": exam_id,
        "student_id": student_id,
        "is_active": False,
    }


# ==========================================
# CONFIGURE A PER-QUESTION TIMER
# ==========================================

@router.patch("/{exam_id}/questions/{question_id}/timer")
def configure_question_timer(
    exam_id: int,
    question_id: int,
    data: QuestionTimerRequest,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can configure question timers.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id).first():
        raise HTTPException(status_code=409, detail="Question timers cannot change after an exam session is created.")
    assignment = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == exam_id,
        ExamQuestion.question_id == question_id,
    ).first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Question is not in this examination bank.")
    assignment.question_time_limit_seconds = data.seconds
    _audit_exam_action(db, current_user.id, "exam_question_timer_configured", {
        "exam_id": exam_id,
        "question_id": question_id,
        "seconds": data.seconds,
    })
    db.commit()
    return {"exam_id": exam_id, "question_id": question_id, "question_time_limit_seconds": assignment.question_time_limit_seconds}


# ==========================================
# UPDATE EXAM CONFIGURATION WITH THREE-REVISION HISTORY
# ==========================================

@router.put("/{exam_id}")
def update_exam_configuration(
    exam_id: int,
    data: ExamCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).with_for_update().first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the examination creator can edit this exam.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id).first():
        raise HTTPException(status_code=409, detail="Exam configuration is locked after a student session is created.")

    revision_count = db.query(ExamConfigurationRevision).filter(
        ExamConfigurationRevision.exam_id == exam_id,
        ExamConfigurationRevision.revision_number > 0,
    ).count()
    if revision_count >= 3:
        raise HTTPException(status_code=409, detail="The three allowed examination configuration revisions have been used.")

    try:
        validate_exam_config(
            data.duration_minutes, data.start_time, data.end_time,
            data.selection_rules, data.total_questions,
            data.gaze_tracking_sensitivity, data.max_tab_switch_warnings,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    assigned_questions = db.query(QuestionBank).join(
        ExamQuestion, ExamQuestion.question_id == QuestionBank.id
    ).filter(ExamQuestion.exam_id == exam_id).all()
    assigned_count = len(assigned_questions)
    if assigned_count < data.total_questions:
        raise HTTPException(status_code=400, detail="The question bank does not contain enough questions for the updated configuration.")
    if data.subject and any(
        (question.subject or "").casefold() != data.subject.casefold()
        for question in assigned_questions
    ):
        raise HTTPException(
            status_code=400,
            detail="The updated examination subject must match every question in its bank.",
        )

    snapshot = {
        "title": data.title,
        "subject": data.subject,
        "duration_minutes": data.duration_minutes,
        "total_questions": data.total_questions,
        "randomize_questions": data.randomize_questions,
        "selection_rules": data.selection_rules,
        "start_time": normalize_schedule_input_to_naive_utc(data.start_time).replace(tzinfo=timezone.utc).isoformat() if data.start_time else None,
        "end_time": normalize_schedule_input_to_naive_utc(data.end_time).replace(tzinfo=timezone.utc).isoformat() if data.end_time else None,
        "negative_marking": data.negative_marking,
        "proctoring_enabled": data.proctoring_enabled,
        "gaze_tracking_sensitivity": data.gaze_tracking_sensitivity,
        "max_tab_switch_warnings": data.max_tab_switch_warnings,
    }
    try:
        db.add(ExamConfigurationRevision(
            exam_id=exam_id,
            revision_number=revision_count + 1,
            configuration_snapshot=snapshot,
            changed_by=current_user.id,
        ))
        _audit_exam_action(db, current_user.id, "exam_configuration_updated", {
            "exam_id": exam_id,
            "revision_number": revision_count + 1,
        })
        exam.title = data.title
        exam.subject = data.subject
        exam.duration_minutes = data.duration_minutes
        exam.total_questions = data.total_questions
        exam.randomize_questions = data.randomize_questions
        exam.selection_rules = data.selection_rules
        exam.start_time = normalize_schedule_input_to_naive_utc(data.start_time)
        exam.end_time = normalize_schedule_input_to_naive_utc(data.end_time)
        exam.negative_marking = data.negative_marking
        exam.proctoring_enabled = data.proctoring_enabled
        exam.gaze_tracking_sensitivity = data.gaze_tracking_sensitivity
        exam.max_tab_switch_warnings = data.max_tab_switch_warnings
        try:
            generate_session_question_ids(
                exam=exam,
                student_id=2147483647,
                db=db,
            )
        except ValueError as error:
            raise HTTPException(
                status_code=400,
                detail=f"Updated configuration cannot generate a valid paper: {error}",
            )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return {"message": "Exam configuration updated.", "exam_id": exam_id, "revision_number": revision_count + 1, "revisions_remaining": 2 - revision_count}


@router.get("/{exam_id}/configuration-revisions")
def list_exam_configuration_revisions(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can view configuration history.")
    rows = db.query(ExamConfigurationRevision).filter(
        ExamConfigurationRevision.exam_id == exam_id
    ).order_by(ExamConfigurationRevision.revision_number.asc()).all()
    revisions_used = sum(1 for row in rows if row.revision_number > 0)
    return {
        "exam_id": exam_id,
        "revision_limit": 3,
        "revisions_used": revisions_used,
        "revisions": [
            {"revision_number": row.revision_number, "configuration": row.configuration_snapshot, "changed_by": row.changed_by, "created_at": row.created_at.replace(tzinfo=timezone.utc) if row.created_at and row.created_at.tzinfo is None else row.created_at}
            for row in rows
        ],
    }


@router.get("/{exam_id}/eligible-students")
def list_eligible_students_for_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """List active Student accounts that the exam creator may assign."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can assign students.")
    students = db.query(User).filter(
        User.role == UserRole.STUDENT.value,
        User.is_active.is_(True),
    ).order_by(User.full_name.asc()).all()
    return {
        "students": [
            {"id": student.id, "full_name": student.full_name, "email": student.email}
            for student in students
        ]
    }


@router.delete("/{exam_id}/assignments/{student_id}")
def remove_exam_assignment(
    exam_id: int,
    student_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Revoke one student's access without deleting exam or attempt history."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can manage assignments.")
    assignment = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.student_id == student_id,
        ExamAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="Active student assignment not found.")
    assignment.is_active = False
    _audit_exam_action(db, current_user.id, "exam_student_access_revoked", {
        "exam_id": exam_id,
        "student_id": student_id,
    })
    db.commit()
    return {"message": "Student access to this examination has been revoked.", "exam_id": exam_id, "student_id": student_id}


@router.get("/{exam_id}/validate-configuration")
def validate_exam_question_configuration(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Check question availability, exact group counts and mark consistency before launch."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the exam creator can validate this configuration.")

    rows = db.query(QuestionBank).join(
        ExamQuestion, ExamQuestion.question_id == QuestionBank.id
    ).filter(ExamQuestion.exam_id == exam_id).all()
    counts = {}
    marks_by_group = {}
    mark_errors = []
    for question in rows:
        question_type = getattr(question.question_type, "value", question.question_type)
        key = f"{question.difficulty}|{question_type}"
        counts[key] = counts.get(key, 0) + 1
        group = (question.difficulty, question_type)
        marks = float(question.marks or 0)
        if group in marks_by_group and not math.isclose(marks_by_group[group], marks, rel_tol=0, abs_tol=0.0001):
            mark_errors.append({
                "group": key,
                "expected_marks": marks_by_group[group],
                "found_marks": marks,
                "question_id": question.id,
            })
        else:
            marks_by_group[group] = marks

    try:
        generate_session_question_ids(
            exam=exam,
            student_id=2147483647,
            db=db,
        )
    except ValueError as error:
        raise HTTPException(
            status_code=409,
            detail=str(error),
        )

    if mark_errors:
        raise HTTPException(
            status_code=409,
            detail={"message": "Question marks are inconsistent within a type/difficulty group.", "errors": mark_errors},
        )

    return {
        "valid": True,
        "exam_id": exam_id,
        "required_questions": exam.total_questions,
        "available_questions": len(rows),
        "available_by_group": counts,
        "selection_rules": exam.selection_rules or {},
        "message": "The configured paper can be generated without reducing any question counts.",
    }


@router.get("/{exam_id}/question-marks")
def get_exam_question_marks(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Return the current maximum marks and their separate revision history."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if current_user.role == UserRole.EXAMINER.value and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can view only your own examination marks.")

    questions = db.query(QuestionBank).join(
        ExamQuestion, ExamQuestion.question_id == QuestionBank.id
    ).filter(ExamQuestion.exam_id == exam_id).all()

    marks_by_group = {}
    group_counts = {}
    for question in questions:
        question_type = getattr(question.question_type, "value", question.question_type)
        key = f"{question.difficulty}|{question_type}"
        marks_by_group.setdefault(key, float(question.marks or 0))
        group_counts[key] = group_counts.get(key, 0) + 1

    revisions = db.query(ExamQuestionMarksRevision).filter(
        ExamQuestionMarksRevision.exam_id == exam_id
    ).order_by(ExamQuestionMarksRevision.revision_number.asc()).all()
    has_sessions = db.query(ExamSession.id).filter(
        ExamSession.exam_id == exam_id
    ).first() is not None
    is_owner = exam.created_by == current_user.id

    return {
        "exam_id": exam_id,
        "marks_by_group": marks_by_group,
        "group_counts": group_counts,
        "revisions_used": len(revisions),
        "revisions_remaining": max(0, 3 - len(revisions)),
        "can_edit": is_owner and not has_sessions,
        "has_sessions": has_sessions,
        "revisions": [
            {
                "revision_number": row.revision_number,
                "marks_snapshot": row.marks_snapshot,
                "changed_by": row.changed_by,
                "created_at": row.created_at,
            }
            for row in revisions
        ],
    }


@router.put("/{exam_id}/question-marks")
def update_exam_question_marks(
    exam_id: int,
    data: dict = Body(...),
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Change the maximum marks for each question type/difficulty group."""
    exam = db.query(Exam).filter(Exam.id == exam_id).with_for_update().first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the examination creator can change question marks.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id).first():
        raise HTTPException(status_code=409, detail="Question marks cannot change after a student session has been created.")

    marks_by_group = data.get("marks_by_group") if isinstance(data, dict) else None
    if not isinstance(marks_by_group, dict) or not marks_by_group:
        raise HTTPException(status_code=400, detail="Enter maximum marks for the question groups.")

    questions = db.query(QuestionBank).join(
        ExamQuestion, ExamQuestion.question_id == QuestionBank.id
    ).filter(ExamQuestion.exam_id == exam_id).all()
    if not questions:
        raise HTTPException(status_code=409, detail="Add questions to the bank before changing question marks.")

    current_groups = {}
    for question in questions:
        question_type = getattr(question.question_type, "value", question.question_type)
        key = f"{question.difficulty}|{question_type}"
        current_groups.setdefault(key, []).append(question)

    if set(marks_by_group) != set(current_groups):
        raise HTTPException(status_code=400, detail="Provide maximum marks for every question group in this examination bank.")

    cleaned_marks = {}
    for key, value in marks_by_group.items():
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise HTTPException(status_code=400, detail=f"Maximum marks for {key} must be a positive number.")
        cleaned_marks[key] = float(value)

    question_ids = [question.id for question in questions]
    shared_question = db.query(ExamQuestion.id).filter(
        ExamQuestion.question_id.in_(question_ids),
        ExamQuestion.exam_id != exam_id,
    ).first()
    if shared_question is not None:
        raise HTTPException(status_code=409, detail="A question is shared with another examination. Its marks cannot be changed here.")

    changed = any(
        not math.isclose(float(question.marks or 0), cleaned_marks[key], rel_tol=0, abs_tol=0.0001)
        for key, group_questions in current_groups.items()
        for question in group_questions
    )
    if not changed:
        return {"message": "The question marks are already set to these values.", "revisions_used": db.query(ExamQuestionMarksRevision).filter(ExamQuestionMarksRevision.exam_id == exam_id).count()}

    revision_count = db.query(ExamQuestionMarksRevision).filter(
        ExamQuestionMarksRevision.exam_id == exam_id
    ).count()
    if revision_count >= 3:
        raise HTTPException(status_code=409, detail="The three allowed question paper marks revisions have been used.")

    for key, group_questions in current_groups.items():
        for question in group_questions:
            question.marks = cleaned_marks[key]

    db.add(ExamQuestionMarksRevision(
        exam_id=exam_id,
        revision_number=revision_count + 1,
        marks_snapshot=cleaned_marks,
        changed_by=current_user.id,
    ))
    _audit_exam_action(db, current_user.id, "exam_question_marks_updated", {
        "exam_id": exam_id,
        "marks_by_group": cleaned_marks,
        "revision_number": revision_count + 1,
    })
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Question marks could not be saved.")
    return {
        "message": "Question paper marks updated successfully.",
        "marks_by_group": cleaned_marks,
        "revisions_used": revision_count + 1,
        "revisions_remaining": max(0, 2 - revision_count),
    }


@router.patch("/{exam_id}/schedule")
def update_exam_schedule(
    exam_id: int,
    data: ExamScheduleUpdate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Allow the examination creator to set or change the schedule before a session starts."""
    exam = db.query(Exam).filter(Exam.id == exam_id).with_for_update().first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="Only the examination creator can schedule this exam.")
    if db.query(ExamSession.id).filter(ExamSession.exam_id == exam_id).first():
        raise HTTPException(
            status_code=409,
            detail="The examination schedule cannot change after a student session has been created.",
        )

    try:
        validate_exam_config(
            exam.duration_minutes,
            data.start_time,
            data.end_time,
            exam.selection_rules,
            exam.total_questions,
            exam.gaze_tracking_sensitivity,
            exam.max_tab_switch_warnings,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))

    exam.start_time = normalize_schedule_input_to_naive_utc(data.start_time)
    exam.end_time = normalize_schedule_input_to_naive_utc(data.end_time)
    _audit_exam_action(db, current_user.id, "examination_scheduled", {
        "exam_id": exam.id,
        "start_time": exam.start_time.isoformat(),
        "end_time": exam.end_time.isoformat(),
    })
    db.commit()

    return {
        "message": "Examination schedule saved.",
        "exam_id": exam.id,
        "start_time": exam.start_time.replace(tzinfo=timezone.utc).isoformat(),
        "end_time": exam.end_time.replace(tzinfo=timezone.utc).isoformat(),
    }




# ==========================================
# DELETE AN EXAMINATION AND ITS RECORDS
# ==========================================

@router.delete("/{exam_id}")
def delete_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Delete an exam and its attempts while keeping shared question-bank questions."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")

    # Only the examination creator can delete this examination.
    if exam.created_by != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You can delete only examinations you created.",
        )

    session_ids = [
        row[0] for row in db.query(ExamSession.id)
        .filter(ExamSession.exam_id == exam_id).all()
    ]
    answer_ids = []
    if session_ids:
        answer_ids = [
            row[0] for row in db.query(Answer.id)
            .filter(Answer.session_id.in_(session_ids)).all()
        ]

    try:
        if answer_ids:
            db.query(AnswerMarkRevision).filter(
                AnswerMarkRevision.answer_id.in_(answer_ids)
            ).delete(synchronize_session=False)

        if session_ids:
            db.query(Result).filter(
                Result.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(ProctorEvent).filter(
                ProctorEvent.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(Answer).filter(
                Answer.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(ExamSession).filter(
                ExamSession.id.in_(session_ids)
            ).delete(synchronize_session=False)

        db.query(ExamAssignment).filter(
            ExamAssignment.exam_id == exam_id
        ).delete(synchronize_session=False)
        db.query(ExamConfigurationRevision).filter(
            ExamConfigurationRevision.exam_id == exam_id
        ).delete(synchronize_session=False)
        db.query(ExamQuestionMarksRevision).filter(
            ExamQuestionMarksRevision.exam_id == exam_id
        ).delete(synchronize_session=False)
        question_ids = [
            row[0] for row in db.query(ExamQuestion.question_id).filter(
                ExamQuestion.exam_id == exam_id
            ).all()
        ]
        db.query(ExamQuestion).filter(
            ExamQuestion.exam_id == exam_id
        ).delete(synchronize_session=False)
        db.flush()

        # Remove exam-owned questions only when no other exam, answer,
        # reusable question, or named question bank still uses them.
        removed_question_ids = []
        for question_id in question_ids:
            question = db.query(QuestionBank).filter(
                QuestionBank.id == question_id
            ).first()
            if question is None or question.created_by != exam.created_by:
                continue

            still_used = (
                db.query(ExamQuestion.id).filter(
                    ExamQuestion.question_id == question_id
                ).first()
                or db.query(Answer.id).filter(
                    Answer.question_id == question_id
                ).first()
                or db.query(QuestionBank.id).filter(
                    QuestionBank.source_question_id == question_id
                ).first()
                or db.query(QuestionCollectionItem.id).filter(
                    QuestionCollectionItem.question_id == question_id
                ).first()
            )
            if still_used:
                continue

            db.delete(question)
            removed_question_ids.append(question_id)

        _audit_exam_action(db, current_user.id, "examination_deleted", {
            "exam_id": exam_id,
            "title": exam.title,
            "deleted_sessions": len(session_ids),
            "deleted_answers": len(answer_ids),
            "removed_unused_questions": removed_question_ids,
        })
        db.delete(exam)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This examination could not be deleted because another record still depends on it.",
        )

    return {
        "message": "The examination and its related records were deleted. Questions still used by another exam or question bank were kept.",
        "exam_id": exam_id,
    }


@router.get("/{exam_id}")
def get_exam_details(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("examiner", "admin")),
):
    """Return examination configuration to authorized staff; Admin access is read-only unless owner."""
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if current_user.role == UserRole.EXAMINER.value and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can view only your own examination configuration.")
    creator = db.query(User).filter(User.id == exam.created_by).first()
    return {
        "id": exam.id,
        "title": exam.title,
        "subject": exam.subject,
        "duration_minutes": exam.duration_minutes,
        "total_questions": exam.total_questions,
        "randomize_questions": exam.randomize_questions,
        "selection_rules": exam.selection_rules or {},
        "start_time": exam.start_time.replace(tzinfo=timezone.utc) if exam.start_time and exam.start_time.tzinfo is None else exam.start_time,
        "end_time": exam.end_time.replace(tzinfo=timezone.utc) if exam.end_time and exam.end_time.tzinfo is None else exam.end_time,
        "negative_marking": exam.negative_marking,
        "proctoring_enabled": exam.proctoring_enabled,
        "gaze_tracking_sensitivity": exam.gaze_tracking_sensitivity,
        "max_tab_switch_warnings": exam.max_tab_switch_warnings,
        "created_by": exam.created_by,
        "created_by_name": creator.full_name if creator else "Unknown",
        "created_by_role": creator.role if creator else None,
        "can_edit": exam.created_by == current_user.id,
    }
