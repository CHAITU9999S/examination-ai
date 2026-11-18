
import json
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import (
    Answer,
    Exam,
    ExamQuestion,
    ExamSession,
    Option,
    QuestionBank,
    Result,
)
from app.services.subjective_grading import auto_generate_ai_suggestions


# ==========================================
# QUESTION TYPES
# ==========================================

OBJECTIVE_QUESTION_TYPES = {
    "MCQ",
    "multi_select",
}

SUBJECTIVE_QUESTION_TYPES = {
    "short_answer",
    "long_answer",
    "image_upload",
}


# ==========================================
# HELPERS
# ==========================================

def _value(value):
    """Convert an enum value to its underlying value."""

    return getattr(value, "value", value)


def _get_session_or_404(
    db: Session,
    session_id: int,
):
    """Retrieve an examination session."""

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination session not found.",
        )

    return session


def _get_session_question_ids(
    db: Session,
    session: ExamSession,
):
    """Retrieve the exact questions selected for this session."""

    if session.selected_question_ids is not None:
        question_ids = session.selected_question_ids

        if (
            not isinstance(question_ids, list)
            or not question_ids
            or any(
                isinstance(question_id, bool)
                or not isinstance(question_id, int)
                or question_id <= 0
                for question_id in question_ids
            )
            or len(question_ids) != len(set(question_ids))
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The saved examination question selection is invalid.",
            )

        return question_ids

    # Compatibility fallback for sessions created before
    # selected_question_ids was populated.
    assignments = db.query(ExamQuestion).filter(
        ExamQuestion.exam_id == session.exam_id,
    ).order_by(
        ExamQuestion.question_order.asc(),
        ExamQuestion.id.asc(),
    ).all()

    if not assignments:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No questions are assigned to this examination.",
        )

    return [
        assignment.question_id
        for assignment in assignments
    ]


def _parse_selected_option_ids(answer_text):
    """Safely parse objective answers stored as JSON option IDs."""

    if not isinstance(answer_text, str):
        return None

    try:
        selected_ids = json.loads(answer_text)
    except (json.JSONDecodeError, TypeError):
        return None

    if not isinstance(selected_ids, list) or not selected_ids:
        return None

    if any(
        isinstance(option_id, bool)
        or not isinstance(option_id, int)
        or option_id <= 0
        for option_id in selected_ids
    ):
        return None

    if len(selected_ids) != len(set(selected_ids)):
        return None

    return selected_ids


# ==========================================
# OBJECTIVE ANSWER EVALUATION
# ==========================================

def evaluate_objective_answer(
    db: Session,
    question: QuestionBank,
    answer: Answer | None,
):
    """
    Automatically evaluate one MCQ or multi-select answer.

    Correct answers receive full marks.
    Incorrect answers receive negative marks when configured.
    Unanswered questions receive zero marks.
    """

    question_type = _value(question.question_type)

    if question_type not in OBJECTIVE_QUESTION_TYPES:
        raise ValueError(
            "Only MCQ and multi-select questions can be "
            "automatically evaluated."
        )

    if answer is None:
        return 0.0

    session = db.query(ExamSession).filter(
        ExamSession.id == answer.session_id,
    ).first()

    exam = (
        db.query(Exam).filter(
            Exam.id == session.exam_id,
        ).first()
        if session is not None
        else None
    )

    negative_marks = (
        float(question.negative_marks or 0)
        if exam is not None and exam.negative_marking
        else 0.0
    )

    selected_ids = _parse_selected_option_ids(
        answer.answer_text,
    )

    if selected_ids is None:
        return -negative_marks

    options = db.query(Option).filter(
        Option.question_id == question.id,
    ).all()

    if not options:
        raise ValueError(
            f"Question {question.id} has no answer options."
        )

    valid_option_ids = {
        option.id
        for option in options
    }

    correct_option_ids = {
        option.id
        for option in options
        if option.is_correct
    }

    if not correct_option_ids:
        raise ValueError(
            f"Question {question.id} has no correct option configured."
        )

    if not set(selected_ids).issubset(valid_option_ids):
        is_correct = False

    elif question_type == "MCQ":
        is_correct = (
            len(selected_ids) == 1
            and set(selected_ids) == correct_option_ids
        )

    else:
        is_correct = (
            set(selected_ids) == correct_option_ids
        )

    if is_correct:
        return float(question.marks)

    return -negative_marks


# ==========================================
# EVALUATE ALL OBJECTIVE ANSWERS
# ==========================================

def evaluate_objective_answers(
    db: Session,
    session_id: int,
):
    """
    Evaluate every objective question in a submitted session.

    Missing objective answers receive zero marks.
    """

    session = _get_session_or_404(
        db,
        session_id,
    )

    if session.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only submitted examination sessions can be evaluated.",
        )

    question_ids = _get_session_question_ids(
        db,
        session,
    )

    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(question_ids),
    ).all()

    question_map = {
        question.id: question
        for question in questions
    }

    if len(question_map) != len(question_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more examination questions could not be found.",
        )

    answers = db.query(Answer).filter(
        Answer.session_id == session_id,
        Answer.question_id.in_(question_ids),
    ).all()

    answer_map = {
        answer.question_id: answer
        for answer in answers
    }

    evaluated_count = 0

    try:
        for question_id in question_ids:
            question = question_map[question_id]

            if _value(question.question_type) not in OBJECTIVE_QUESTION_TYPES:
                continue

            answer = answer_map.get(question_id)

            awarded_marks = evaluate_objective_answer(
                db,
                question,
                answer,
            )

            if answer is not None:
                answer.awarded_marks = awarded_marks

            evaluated_count += 1

        db.commit()

        return {
            "session_id": session_id,
            "evaluated_objective_questions": evaluated_count,
            "message": "Objective answers evaluated successfully.",
        }

    except (ValueError, SQLAlchemyError):
        db.rollback()
        raise


# ==========================================
# RESULT CALCULATION
# ==========================================

def calculate_session_result(
    db: Session,
    session_id: int,
):
    """
    Calculate and save the final examination result.

    Result finalization waits until every answered subjective
    question has received marks.

    Unanswered questions receive zero marks.
    """

    session = _get_session_or_404(
        db,
        session_id,
    )

    if session.status != "submitted":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The examination must be submitted before result calculation.",
        )

    question_ids = _get_session_question_ids(
        db,
        session,
    )

    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(question_ids),
    ).all()

    question_map = {
        question.id: question
        for question in questions
    }

    if len(question_map) != len(question_ids):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="One or more examination questions could not be found.",
        )

    answers = db.query(Answer).filter(
        Answer.session_id == session_id,
        Answer.question_id.in_(question_ids),
    ).all()

    answer_map = {
        answer.question_id: answer
        for answer in answers
    }

    pending_subjective = []

    try:
        # Calculate objective answers first.
        for question_id in question_ids:
            question = question_map[question_id]
            question_type = _value(question.question_type)

            if question_type in OBJECTIVE_QUESTION_TYPES:
                answer = answer_map.get(question_id)

                awarded_marks = evaluate_objective_answer(
                    db,
                    question,
                    answer,
                )

                if answer is not None:
                    answer.awarded_marks = awarded_marks

            elif question_type in SUBJECTIVE_QUESTION_TYPES:
                answer = answer_map.get(question_id)

                # Unanswered subjective questions receive zero.
                if answer is not None and answer.awarded_marks is None:
                    pending_subjective.append(question_id)

            else:
                raise ValueError(
                    f"Unsupported question type: {question_type}"
                )

        # Do not publish an incomplete result.
        if pending_subjective:
            db.commit()

            return {
                "session_id": session_id,
                "status": "pending_subjective_grading",
                "pending_question_ids": pending_subjective,
                "message": (
                    "Some subjective answers still require grading."
                ),
            }

        # Total marks include every selected question.
        total_marks = sum(
            float(question_map[question_id].marks or 0)
            for question_id in question_ids
        )

        # Unanswered questions contribute zero.
        obtained_marks = sum(
            float(answer_map[question_id].awarded_marks or 0)
            for question_id in question_ids
            if question_id in answer_map
        )

        percentage = (
            (obtained_marks / total_marks) * 100
            if total_marks > 0
            else 0.0
        )

        # Persist the complete per-question breakdown with the final result.
        question_scores = []
        for question_id in question_ids:
            question = question_map[question_id]
            answer = answer_map.get(question_id)
            question_type = _value(question.question_type)
            if answer is None:
                grading_status = "unanswered"
                awarded = 0.0
            else:
                awarded = float(answer.awarded_marks or 0)
                grading_status = (
                    "graded"
                    if question_type in SUBJECTIVE_QUESTION_TYPES
                    else "evaluated"
                )

            question_scores.append({
                "question_id": question_id,
                "question_type": question_type,
                "maximum_marks": float(question.marks or 0),
                "awarded_marks": awarded,
                "status": grading_status,
            })

        result = db.query(Result).filter(
            Result.session_id == session_id,
        ).with_for_update().first()

        if result is None:
            result = Result(
                session_id=session_id,
                total_marks=total_marks,
                obtained_marks=obtained_marks,
                percentage=percentage,
                question_scores=question_scores,
                evaluated_at=datetime.utcnow(),
            )

            db.add(result)

        else:
            result.total_marks = total_marks
            result.obtained_marks = obtained_marks
            result.percentage = percentage
            result.question_scores = question_scores
            result.evaluated_at = datetime.utcnow()

        db.commit()
        db.refresh(result)

        return {
            "session_id": session_id,
            "status": "evaluated",
            "total_marks": result.total_marks,
            "obtained_marks": result.obtained_marks,
            "percentage": result.percentage,
            "question_scores": result.question_scores,
            "message": "Examination result calculated successfully.",
        }

    except (ValueError, SQLAlchemyError):
        db.rollback()
        raise


# ==========================================
# COMPLETE EVALUATION WORKFLOW
# ==========================================

def evaluate_exam_session(
    db: Session,
    session_id: int,
):
    """
    Run objective evaluation followed by result calculation.
    """

    objective_result = evaluate_objective_answers(
        db,
        session_id,
    )

    ai_grading = auto_generate_ai_suggestions(
        db,
        session_id,
    )

    result = calculate_session_result(
        db,
        session_id,
    )

    return {
        "objective_evaluation": objective_result,
        "ai_grading": ai_grading,
        "result": result,
    }
