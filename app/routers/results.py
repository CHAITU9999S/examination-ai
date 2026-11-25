from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
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


def _get_cohort_distribution(db: Session, exam_id: int, current_result_id: int):
    """Return anonymized score-band counts for published results only."""
    rows = db.query(Result).join(
        ExamSession,
        Result.session_id == ExamSession.id,
    ).filter(
        ExamSession.exam_id == exam_id,
        Result.is_published.is_(True),
    ).all()

    buckets = [
        {"label": f"{index * 10}-{(index + 1) * 10}%", "count": 0}
        for index in range(10)
    ]

    current_percentage = None
    for row in rows:
        total = float(row.total_marks or 0)
        obtained = float(row.obtained_marks or 0)
        percentage = (
            max(0.0, min(100.0, obtained / total * 100))
            if total > 0
            else 0.0
        )
        bucket_index = min(9, int(percentage // 10))
        buckets[bucket_index]["count"] += 1
        if row.id == current_result_id:
            current_percentage = round(percentage, 2)

    cohort_size = len(rows)
    for bucket in buckets:
        bucket["share_percentage"] = (
            round(bucket["count"] / cohort_size * 100, 2)
            if cohort_size
            else 0.0
        )

    return {
        "cohort_size": cohort_size,
        "current_student_percentage": current_percentage,
        "score_bands": buckets,
    }


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
                "grade": result.grade or _letter_grade(result.percentage),
                "percentile": _get_percentile(
                    db,
                    exam.id,
                    float(result.obtained_marks or 0),
                ),
                "face_photo_url": f"/results/sessions/{session.id}/face-photo" if session.face_capture_data else None,
            }
            for result, session, exam in rows
        ]
    }


@router.get("/sessions/{session_id}/face-photo")
def get_my_result_face_photo(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Serve a captured face photo only to the student with a published result."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Examination session not found.")
    _require_student_result_access(session, current_user, db)
    if not session.face_capture_data:
        raise HTTPException(status_code=404, detail="No face capture is available for this result.")
    return Response(
        content=session.face_capture_data,
        media_type=session.face_capture_mime_type or "image/jpeg",
        headers={"Cache-Control": "private, no-store"},
    )


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
            "student_answer": answer.answer_text if answer else None,
            "outcome": outcome,
            "examiner_feedback": (
                answer.examiner_feedback if answer else None
            ),
            "image_annotations": (
                answer.image_annotations if answer else None
            ),
            "rubric_scores": (
                answer.rubric_scores if answer else None
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
        "face_photo_url": f"/results/sessions/{session.id}/face-photo" if session.face_capture_data else None,
        "total_marks": result.total_marks,
        "obtained_marks": result.obtained_marks,
        "percentage": result.percentage,
        "grade": result.grade or _letter_grade(result.percentage),
        "percentile": percentile,
        "cohort_distribution": _get_cohort_distribution(
            db,
            session.exam_id,
            result.id,
        ),
        "question_results": question_results,
    }


def _letter_grade(percentage):
    score = float(percentage or 0)
    if score >= 90:
        return "A+"
    if score >= 80:
        return "A"
    if score >= 70:
        return "B"
    if score >= 60:
        return "C"
    if score >= 50:
        return "D"
    return "F"


@router.get("/exams/{exam_id}")
def get_exam_results_for_staff(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return student-by-student result status for the exam owner or Admin."""
    role = getattr(current_user.role, "value", current_user.role)
    if not current_user.is_active or role not in {"admin", "examiner"}:
        raise HTTPException(status_code=403, detail="Only active exam staff can view examination results.")

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Exam not found.")
    if role == "examiner" and exam.created_by != current_user.id:
        raise HTTPException(status_code=403, detail="You can view results only for examinations you created.")

    rows = db.query(ExamSession, User, Result).join(
        User, User.id == ExamSession.student_id
    ).outerjoin(
        Result, Result.session_id == ExamSession.id
    ).filter(
        ExamSession.exam_id == exam_id
    ).order_by(
        ExamSession.submitted_at.desc(),
        ExamSession.id.desc(),
    ).all()

    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "total_students": len(rows),
        "results": [
            {
                "session_id": session.id,
                "student_id": student.id,
                "student_name": student.full_name,
                "session_status": session.status,
                "submitted_at": session.submitted_at,
                "face_photo_available": bool(session.face_capture_data),
                "face_photo_url": f"/grading/sessions/{session.id}/face-photo" if session.face_capture_data else None,
                "result_published": bool(result and result.is_published),
                "total_marks": result.total_marks if result else None,
                "obtained_marks": result.obtained_marks if result else None,
                "percentage": result.percentage if result else None,
                "grade": (result.grade or _letter_grade(result.percentage)) if result and result.is_published else None,
            }
            for session, student, result in rows
        ],
    }


@router.get("/staff/history")
def get_staff_result_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return historical examination performance visible to this staff member."""
    role = getattr(current_user.role, "value", current_user.role)
    if not current_user.is_active or role not in {"admin", "examiner"}:
        raise HTTPException(status_code=403, detail="Only active exam staff can view result history.")

    query = db.query(Result, ExamSession, Exam, User).join(
        ExamSession, Result.session_id == ExamSession.id
    ).join(
        Exam, Exam.id == ExamSession.exam_id
    ).join(
        User, User.id == ExamSession.student_id
    )
    if role == "examiner":
        query = query.filter(Exam.created_by == current_user.id)

    rows = query.order_by(
        ExamSession.submitted_at.desc(),
        Result.id.desc(),
    ).limit(1000).all()

    return {
        "total": len(rows),
        "results": [
            {
                "result_id": result.id,
                "session_id": session.id,
                "exam_id": exam.id,
                "exam_title": exam.title,
                "student_id": student.id,
                "student_name": student.full_name,
                "submitted_at": session.submitted_at,
                "published": bool(result.is_published),
                "total_marks": result.total_marks,
                "obtained_marks": result.obtained_marks,
                "percentage": result.percentage,
                "grade": (result.grade or _letter_grade(result.percentage)) if result.is_published else None,
            }
            for result, session, exam, student in rows
        ],
    }
