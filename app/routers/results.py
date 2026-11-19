from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Answer, Exam, ExamSession, QuestionBank, Result, User


router = APIRouter(
    prefix="/results",
    tags=["Student Results"],
)


def _require_student_result_access(
    session: ExamSession,
    current_user: User,
    db: Session,
):
    if current_user.role != "student" or session.student_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You can only view your own examination results.",
        )

    result = db.query(Result).filter(
        Result.session_id == session.id,
    ).first()

    if result is None or not result.is_published:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The result is not available yet.",
        )

    return result


def _get_percentile(db: Session, exam_id: int, obtained_marks: float):
    cohort_query = db.query(Result).join(
        ExamSession,
        Result.session_id == ExamSession.id,
    ).filter(
        ExamSession.exam_id == exam_id,
        Result.is_published.is_(True),
    )

    cohort_size = cohort_query.count()
    if cohort_size == 0:
        return 0.0

    at_or_below = cohort_query.filter(
        Result.obtained_marks <= obtained_marks,
    ).count()

    return round((at_or_below / cohort_size) * 100, 2)


@router.get("/me")
def get_my_published_results(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """List only this student's published examination results."""

    if current_user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only students can access the student results dashboard.",
        )

    rows = db.query(
        Result,
        ExamSession,
        Exam,
    ).join(
        ExamSession,
        Result.session_id == ExamSession.id,
    ).join(
        Exam,
        ExamSession.exam_id == Exam.id,
    ).filter(
        ExamSession.student_id == current_user.id,
        Result.is_published.is_(True),
    ).order_by(
        Result.published_at.desc(),
        Result.id.desc(),
    ).all()

    return {
        "results": [
            {
                "result_id": result.id,
                "session_id": session.id,
                "exam_id": exam.id,
                "exam_title": exam.title,
                "subject": exam.subject,
                "submitted_at": session.submitted_at,
                "published_at": result.published_at,
                "total_marks": result.total_marks,
                "obtained_marks": result.obtained_marks,
                "percentage": result.percentage,
                "percentile": _get_percentile(
                    db,
                    exam.id,
                    float(result.obtained_marks or 0),
                ),
            }
            for result, session, exam in rows
        ]
    }


@router.get("/{session_id}")
def get_my_result_details(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return published score details and examiner feedback to the owner."""

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
    ).first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examination session not found.",
        )

    result = _require_student_result_access(
        session,
        current_user,
        db,
    )

    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    answers = db.query(Answer).filter(
        Answer.session_id == session.id,
    ).all()
    answer_map = {answer.question_id: answer for answer in answers}

    question_ids = [
        item.get("question_id")
        for item in (result.question_scores or [])
        if isinstance(item, dict) and item.get("question_id") is not None
    ]
    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(question_ids or [-1]),
    ).all()
    question_map = {question.id: question for question in questions}

    question_results = []
    for score in result.question_scores or []:
        if not isinstance(score, dict):
            continue

        question_id = score.get("question_id")
        question = question_map.get(question_id)
        answer = answer_map.get(question_id)
        maximum = float(score.get("maximum_marks") or 0)
        awarded = float(score.get("awarded_marks") or 0)

        if score.get("status") == "unanswered":
            outcome = "unanswered"
        elif awarded >= maximum:
            outcome = "correct"
        elif awarded <= 0:
            outcome = "incorrect"
        else:
            outcome = "partial"

        question_results.append({
            **score,
            "question_text": question.question_text if question else None,
            "outcome": outcome,
            "examiner_feedback": (
                answer.examiner_feedback if answer else None
            ),
            "image_annotations": (
                answer.image_annotations if answer else None
            ),
        })

    percentile = _get_percentile(
        db,
        session.exam_id,
        float(result.obtained_marks or 0),
    )

    return {
        "result_id": result.id,
        "session_id": session.id,
        "exam_id": session.exam_id,
        "exam_title": exam.title if exam else None,
        "submitted_at": session.submitted_at,
        "published_at": result.published_at,
        "total_marks": result.total_marks,
        "obtained_marks": result.obtained_marks,
        "percentage": result.percentage,
        "percentile": percentile,
        "question_results": question_results,
    }
