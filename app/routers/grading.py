
import json
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import (
    Answer,
    Exam,
    ExamSession,
    Option,
    QuestionBank,
    Result,
    User,
)


router = APIRouter(
    prefix="/grading",
    tags=["Exam Grading"],
)


# ==========================================
# REQUEST SCHEMA
# ==========================================

class ManualGradeSubmission(BaseModel):
    awarded_marks: float = Field(
        ge=0,
        allow_inf_nan=False,
    )


# ==========================================
# AUTHORIZATION
# ==========================================

def require_examiner_or_admin(user: User):
    """Allow only examiners and administrators."""

    role = getattr(user.role, "value", user.role)

    if role not in {"examiner", "admin"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only examiners and administrators can access grading.",
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


# ==========================================
# OBJECTIVE ANSWER EVALUATION
# ==========================================

def evaluate_objective_answer(
    answer: Answer,
    question: QuestionBank,
    exam: Exam,
) -> float:
    """Evaluate MCQ and multiple-select answers."""

    question_type = getattr(
        question.question_type,
        "value",
        question.question_type,
    )

    selected_ids = set()

    try:
        if question_type == "MCQ":
            selected_id = int(answer.answer_text)
            selected_ids = {selected_id}

        elif question_type == "multi_select":
            parsed = json.loads(answer.answer_text)

            if (
                not isinstance(parsed, list)
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, int)
                    for item in parsed
                )
            ):
                raise ValueError("Invalid option selection.")

            if len(parsed) != len(set(parsed)):
                raise ValueError("Duplicate option selection.")

            selected_ids = set(parsed)

        else:
            raise ValueError("Unsupported objective question type.")

    except (TypeError, ValueError, json.JSONDecodeError):
        selected_ids = set()

    options = db_options = None

    # Load the correct options for this question.
    # This query is performed through the answer's session database
    # in the calling function, which supplies the option list.
    raise RuntimeError(
        "Use evaluate_objective_answer_with_options instead."
    )


def evaluate_objective_answer_with_options(
    answer: Answer,
    question: QuestionBank,
    exam: Exam,
    options: list[Option],
) -> float:
    """Calculate marks using the saved option correctness values."""

    question_type = getattr(
        question.question_type,
        "value",
        question.question_type,
    )

    correct_ids = {
        option.id
        for option in options
        if option.is_correct
    }

    try:
        if question_type == "MCQ":
            selected_ids = {int(answer.answer_text)}

        elif question_type == "multi_select":
            parsed = json.loads(answer.answer_text)

            if (
                not isinstance(parsed, list)
                or any(
                    isinstance(item, bool)
                    or not isinstance(item, int)
                    for item in parsed
                )
                or len(parsed) != len(set(parsed))
            ):
                raise ValueError("Invalid multiple-select answer.")

            selected_ids = set(parsed)

        else:
            raise ValueError("Unsupported objective question type.")

    except (TypeError, ValueError, json.JSONDecodeError):
        selected_ids = set()

    if not selected_ids.issubset({option.id for option in options}):
        selected_ids = set()

    is_correct = (
        bool(correct_ids)
        and selected_ids == correct_ids
    )

    if is_correct:
        return float(question.marks or 0)

    if exam.negative_marking:
        return -float(question.negative_marks or 0)

    return 0.0


# ==========================================
# RESULT CALCULATION
# ==========================================

def update_session_result(
    session: ExamSession,
    exam: Exam,
    db: Session,
):
    """Save a result only after every assigned question is evaluated."""

    selected_ids = session.selected_question_ids

    if not isinstance(selected_ids, list) or not selected_ids:
        return None

    answers = db.query(Answer).filter(
        Answer.session_id == session.id,
        Answer.question_id.in_(selected_ids),
    ).all()

    answer_by_question = {
        answer.question_id: answer
        for answer in answers
    }

    if len(answer_by_question) != len(selected_ids):
        return None

    if any(
        answer_by_question[question_id].awarded_marks is None
        for question_id in selected_ids
    ):
        return None

    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(selected_ids),
    ).all()

    if len(questions) != len(selected_ids):
        return None

    total_marks = sum(
        float(question.marks or 0)
        for question in questions
    )

    obtained_marks = sum(
        float(answer_by_question[question_id].awarded_marks)
        for question_id in selected_ids
    )

    percentage = (
        (obtained_marks / total_marks) * 100
        if total_marks > 0
        else 0
    )

    result = db.query(Result).filter(
        Result.session_id == session.id,
    ).first()

    if result is None:
        result = Result(
            session_id=session.id,
            total_marks=total_marks,
            obtained_marks=obtained_marks,
            percentage=percentage,
            evaluated_at=datetime.utcnow(),
        )
        db.add(result)

    else:
        result.total_marks = total_marks
        result.obtained_marks = obtained_marks
        result.percentage = percentage
        result.evaluated_at = datetime.utcnow()

    return result


# ==========================================
# PENDING SUBJECTIVE ANSWERS
# ==========================================

@router.get("/exams/{exam_id}/pending")
def get_pending_subjective_answers(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List subjective answers awaiting examiner grading."""

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
                "maximum_marks": question.marks,
                "model_answer": question.model_answer_text,
                "submitted_at": session.submitted_at,
            }
            for answer, session, question in rows
        ],
    }


# ==========================================
# AUTOMATIC OBJECTIVE GRADING
# ==========================================

@router.post("/sessions/{session_id}/evaluate-objective")
def evaluate_session_objective_answers(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Evaluate all unanswered MCQ and multiple-select responses."""

    require_examiner_or_admin(current_user)

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
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
            detail="Only submitted examination sessions can be evaluated.",
        )

    selected_ids = session.selected_question_ids

    if not isinstance(selected_ids, list) or not selected_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The session has no valid saved question paper.",
        )

    try:
        answers = db.query(Answer).filter(
            Answer.session_id == session.id,
            Answer.question_id.in_(selected_ids),
        ).all()

        questions = db.query(QuestionBank).filter(
            QuestionBank.id.in_(selected_ids),
        ).all()

        question_by_id = {
            question.id: question
            for question in questions
        }

        evaluated_count = 0

        for answer in answers:
            question = question_by_id.get(answer.question_id)

            if question is None or answer.awarded_marks is not None:
                continue

            question_type = getattr(
                question.question_type,
                "value",
                question.question_type,
            )

            if question_type not in {"MCQ", "multi_select"}:
                continue

            options = db.query(Option).filter(
                Option.question_id == question.id,
            ).all()

            answer.awarded_marks = evaluate_objective_answer_with_options(
                answer,
                question,
                exam,
                options,
            )

            evaluated_count += 1

        result = update_session_result(
            session,
            exam,
            db,
        )

        db.commit()

        if result is not None:
            db.refresh(result)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to evaluate objective answers.",
        )

    return {
        "message": "Objective answer evaluation completed.",
        "session_id": session.id,
        "evaluated_answers": evaluated_count,
        "result_ready": result is not None,
        "result": (
            {
                "total_marks": result.total_marks,
                "obtained_marks": result.obtained_marks,
                "percentage": result.percentage,
            }
            if result is not None
            else None
        ),
    }


# ==========================================
# MANUAL SUBJECTIVE GRADING
# ==========================================

@router.post("/answers/{answer_id}/grade")
def grade_subjective_answer(
    answer_id: int,
    submission: ManualGradeSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Allow an authorized examiner/admin to grade a subjective answer."""

    require_examiner_or_admin(current_user)

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

    question_type = getattr(
        question.question_type,
        "value",
        question.question_type,
    )

    if question_type not in {"short_answer", "long_answer"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Manual grading is only available for subjective answers.",
        )

    maximum_marks = float(question.marks or 0)

    if submission.awarded_marks > maximum_marks:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Marks cannot exceed {maximum_marks}.",
        )

    try:
        answer.awarded_marks = submission.awarded_marks

        result = update_session_result(
            session,
            exam,
            db,
        )

        db.commit()

        if result is not None:
            db.refresh(result)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to save the awarded marks.",
        )

    return {
        "message": "Answer graded successfully.",
        "answer_id": answer.id,
        "session_id": session.id,
        "question_id": question.id,
        "awarded_marks": answer.awarded_marks,
        "maximum_marks": maximum_marks,
        "result_ready": result is not None,
        "result": (
            {
                "total_marks": result.total_marks,
                "obtained_marks": result.obtained_marks,
                "percentage": result.percentage,
            }
            if result is not None
            else None
        ),
    }
