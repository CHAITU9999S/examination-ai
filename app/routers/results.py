from datetime import datetime, timezone
import json

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Answer, Exam, ExamAssignment, ExamSession, Option, QuestionBank, Result, User
from app.services.exam_config import normalize_to_naive_utc
from app.services.session_service import generate_session_question_ids


router = APIRouter(
    prefix="/results",
    tags=["Student Results"],
)


def _exam_attribution(session: ExamSession, exam: Exam | None, db: Session) -> dict:
    creator = db.query(User).filter(User.id == exam.created_by).first() if exam else None
    assignment = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == session.exam_id,
        ExamAssignment.student_id == session.student_id,
    ).first()
    assigner = (
        db.query(User).filter(User.id == assignment.assigned_by).first()
        if assignment is not None else None
    )
    return {
        "creator_name": creator.full_name if creator else "Unknown",
        "creator_role": creator.role if creator else None,
        "assigned_by_name": assigner.full_name if assigner else "Unknown",
        "assigned_by_role": assigner.role if assigner else None,
    }


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


def _require_published_result_for_submitted_report(session: ExamSession | None, db: Session):
    """Do not expose answer keys for submitted attempts before result publication."""
    if session is None:
        return
    is_submitted = (
        session.status in {"submitted", "auto_submitted"}
        or (session.submitted_at is not None and session.status != "expired")
    )
    if not is_submitted:
        return
    published_result = db.query(Result).filter(
        Result.session_id == session.id,
        Result.is_published.is_(True),
    ).first()
    if published_result is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The examination result is not published yet.",
        )


def _student_report_image_response(question, session, kind: str, db: Session):
    """Serve a student's own post-exam question, answer, or model-answer image."""
    if kind == "question":
        image_data = question.question_image_data
        mime_type = question.question_image_mime_type
    elif kind == "expected":
        image_data = question.expected_answer_image_data
        mime_type = question.expected_answer_image_mime_type
    elif kind == "student":
        if session is None:
            raise HTTPException(status_code=404, detail="No submitted answer image is available.")
        answer = db.query(Answer).filter(
            Answer.session_id == session.id,
            Answer.question_id == question.id,
        ).first()
        image_data = answer.image_data if answer else None
        mime_type = answer.image_mime_type if answer else None
    else:
        raise HTTPException(status_code=400, detail="Unsupported report image type.")

    if not image_data:
        raise HTTPException(status_code=404, detail="This report image is not available.")
    return Response(
        content=image_data,
        media_type=mime_type or "application/octet-stream",
        headers={"Cache-Control": "private, no-store"},
    )


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


@router.get("/session-status/{session_id}")
def get_my_result_session_status(
    session_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return non-sensitive status for a student's own examination session."""
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Examination session not found.")
    if current_user.role != "student" or session.student_id != current_user.id:
        raise HTTPException(status_code=403, detail="You can only view your own examination performance.")
    exam = db.query(Exam).filter(Exam.id == session.exam_id).first()
    result = db.query(Result).filter(
        Result.session_id == session.id,
        Result.is_published.is_(True),
    ).first()
    return {
        "session_id": session.id,
        "exam_id": session.exam_id,
        "exam_title": exam.title if exam else "Examination",
        "subject": exam.subject if exam else None,
        **_exam_attribution(session, exam, db),
        "session_status": session.status,
        "submitted_at": session.submitted_at,
        "result_published": bool(result),
    }


@router.get("/exams/{exam_id}/paper/{question_id}/image/{kind}")
def get_my_ended_exam_paper_image(
    exam_id: int,
    question_id: int,
    kind: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can view their assigned question papers.")
    assignment = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.student_id == current_user.id,
        ExamAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="No active assignment was found for this examination.")
    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")
    exam_end = normalize_to_naive_utc(exam.end_time)
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    if exam_end is None or now < exam_end:
        raise HTTPException(status_code=403, detail="Report images are available after the examination schedule ends.")
    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == current_user.id,
    ).order_by(ExamSession.id.desc()).first()
    _require_published_result_for_submitted_report(session, db)
    selected_ids = (
        list(session.selected_question_ids)
        if session is not None and isinstance(session.selected_question_ids, list)
        else generate_session_question_ids(exam, current_user.id, db)
    )
    if question_id not in selected_ids:
        raise HTTPException(status_code=404, detail="Question not found in your assigned paper.")
    question = db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return _student_report_image_response(question, session, kind, db)


@router.get("/sessions/{session_id}/questions/{question_id}/image/{kind}")
def get_my_published_result_image(
    session_id: int,
    question_id: int,
    kind: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = db.query(ExamSession).filter(ExamSession.id == session_id).first()
    if session is None:
        raise HTTPException(status_code=404, detail="Examination session not found.")
    _require_student_result_access(session, current_user, db)
    if question_id not in (session.selected_question_ids or []):
        raise HTTPException(status_code=404, detail="Question not found in your examination paper.")
    question = db.query(QuestionBank).filter(QuestionBank.id == question_id).first()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found.")
    return _student_report_image_response(question, session, kind, db)


@router.get("/exams/{exam_id}/paper")
def get_my_ended_exam_paper(
    exam_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return an assigned student's paper and answers only after the exam ends."""
    if current_user.role != "student":
        raise HTTPException(status_code=403, detail="Only students can view their assigned question papers.")

    assignment = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.student_id == current_user.id,
        ExamAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="No active assignment was found for this examination.")

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")

    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == current_user.id,
    ).order_by(ExamSession.id.desc()).first()
    _require_published_result_for_submitted_report(session, db)

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    exam_end = normalize_to_naive_utc(exam.end_time)
    if exam_end is None or now < exam_end:
        raise HTTPException(status_code=403, detail="The question paper and answers are available after the examination schedule ends.")

    try:
        selected_ids = (
            list(session.selected_question_ids)
            if session is not None and isinstance(session.selected_question_ids, list)
            else generate_session_question_ids(exam, current_user.id, db)
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))
    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(selected_ids or [-1]),
    ).all()
    question_map = {question.id: question for question in questions}
    if len(question_map) != len(selected_ids):
        raise HTTPException(status_code=409, detail="One or more assigned questions are no longer available.")

    answers = db.query(Answer).filter(
        Answer.session_id == session.id,
    ).all() if session is not None else []
    answer_map = {answer.question_id: answer for answer in answers}
    published_result = (
        db.query(Result).filter(
            Result.session_id == session.id,
            Result.is_published.is_(True),
        ).first()
        if session is not None else None
    )
    paper = []
    for question_id in selected_ids:
        question = question_map[question_id]
        options = db.query(Option).filter(
            Option.question_id == question_id
        ).order_by(Option.id).all()
        answer = answer_map.get(question_id)
        paper.append({
            "question_id": question.id,
            "question_text": question.question_text,
            "question_type": getattr(question.question_type, "value", question.question_type),
            "maximum_marks": float(question.marks or 0),
            "awarded_marks": answer.awarded_marks if answer and published_result else None,
            "student_answer": answer.answer_text if answer else None,
            "correct_answer": question.expected_answer or question.model_answer_text,
            "correct_options": [option.option_text for option in options if option.is_correct],
            "options": [option.option_text for option in options],
            "question_image_available": bool(question.question_image_data),
            "question_image_url": f"/results/exams/{exam.id}/paper/{question.id}/image/question" if question.question_image_data else None,
            "expected_answer_image_available": bool(question.expected_answer_image_data),
            "expected_answer_image_url": f"/results/exams/{exam.id}/paper/{question.id}/image/expected" if question.expected_answer_image_data else None,
            "student_answer_image_url": f"/results/exams/{exam.id}/paper/{question.id}/image/student" if answer and answer.image_data else None,
        })

    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "subject": exam.subject,
        "session_id": session.id if session else None,
        "session_status": session.status if session else "not_attempted",
        "paper": paper,
    }


@router.get("/exams/{exam_id}/students/{student_id}/paper")
def get_admin_student_assigned_paper(
    exam_id: int,
    student_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return a student's assigned paper and answers for Admin performance review."""
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only Admins can view global student performance reports.")

    assignment = db.query(ExamAssignment).filter(
        ExamAssignment.exam_id == exam_id,
        ExamAssignment.student_id == student_id,
        ExamAssignment.is_active.is_(True),
    ).first()
    if assignment is None:
        raise HTTPException(status_code=404, detail="This examination is not actively assigned to the selected student.")

    exam = db.query(Exam).filter(Exam.id == exam_id).first()
    if exam is None:
        raise HTTPException(status_code=404, detail="Examination not found.")

    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == student_id,
    ).order_by(ExamSession.id.desc()).first()
    try:
        selected_ids = (
            list(session.selected_question_ids)
            if session is not None and isinstance(session.selected_question_ids, list) and session.selected_question_ids
            else generate_session_question_ids(exam, student_id, db)
        )
    except ValueError as error:
        raise HTTPException(status_code=409, detail=str(error))

    questions = db.query(QuestionBank).filter(
        QuestionBank.id.in_(selected_ids or [-1]),
    ).all()
    question_map = {question.id: question for question in questions}
    if len(question_map) != len(selected_ids):
        raise HTTPException(status_code=409, detail="One or more questions in the assigned paper are no longer available.")

    answers = db.query(Answer).filter(
        Answer.session_id == session.id,
    ).all() if session is not None else []
    answer_map = {answer.question_id: answer for answer in answers}
    result = db.query(Result).filter(
        Result.session_id == session.id,
    ).first() if session is not None else None

    paper = []
    for order, question_id in enumerate(selected_ids, start=1):
        question = question_map[question_id]
        options = db.query(Option).filter(
            Option.question_id == question_id,
        ).order_by(Option.id).all()
        answer = answer_map.get(question_id)
        selected_option_texts = []
        if answer is not None and getattr(question.question_type, "value", question.question_type) in {"MCQ", "multi_select"}:
            try:
                selected_option_ids = json.loads(answer.answer_text or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                selected_option_ids = []
            if isinstance(selected_option_ids, int):
                selected_option_ids = [selected_option_ids]
            if isinstance(selected_option_ids, list):
                selected_map = {option.id: option.option_text for option in options}
                for option_id in selected_option_ids:
                    try:
                        normalized_id = int(option_id)
                    except (TypeError, ValueError):
                        continue
                    if normalized_id in selected_map:
                        selected_option_texts.append(selected_map[normalized_id])

        paper.append({
            "question_id": question.id,
            "question_order": order,
            "question_text": question.question_text,
            "question_type": getattr(question.question_type, "value", question.question_type),
            "difficulty": question.difficulty,
            "maximum_marks": float(question.marks or 0),
            "awarded_marks": float(answer.awarded_marks) if answer is not None and answer.awarded_marks is not None else None,
            "student_answer": answer.answer_text if answer is not None else None,
            "student_selected_options": selected_option_texts,
            "correct_answer": question.expected_answer or question.model_answer_text,
            "correct_options": [option.option_text for option in options if option.is_correct],
            "options": [option.option_text for option in options],
            "question_image_available": bool(question.question_image_data),
            "expected_answer_image_available": bool(question.expected_answer_image_data),
            "student_answer_image_available": bool(answer and answer.image_data),
        })

    calculated_total = round(sum(item["maximum_marks"] for item in paper), 2)
    return {
        "exam_id": exam.id,
        "exam_title": exam.title,
        "subject": exam.subject,
        "student_id": student_id,
        "session_id": session.id if session else None,
        "session_status": session.status if session else "not_attempted",
        "result_published": bool(result and result.is_published),
        "obtained_marks": float(result.obtained_marks) if result and result.obtained_marks is not None else None,
        "total_marks": float(result.total_marks) if result and result.total_marks is not None else calculated_total,
        "percentage": float(result.percentage) if result and result.percentage is not None else None,
        "grade": result.grade if result and result.is_published else None,
        "paper": paper,
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

        option_rows = (
            db.query(Option.id, Option.option_text, Option.is_correct)
            .filter(Option.question_id == question_id)
            .order_by(Option.id)
            .all()
            if question is not None else []
        )
        correct_options = [
            option_text for _, option_text, is_correct in option_rows if is_correct
        ]
        student_selected_options = []
        if answer is not None and question is not None and getattr(question.question_type, "value", question.question_type) in {"MCQ", "multi_select"}:
            try:
                selected_option_ids = json.loads(answer.answer_text or "[]")
            except (TypeError, ValueError, json.JSONDecodeError):
                selected_option_ids = []
            if isinstance(selected_option_ids, int):
                selected_option_ids = [selected_option_ids]
            if isinstance(selected_option_ids, list):
                normalized_option_ids = []
                for option_id in selected_option_ids:
                    try:
                        normalized_option_ids.append(int(option_id))
                    except (TypeError, ValueError):
                        continue
                selected_option_map = {
                    option_id: option_text for option_id, option_text, _ in option_rows
                }
                student_selected_options = [
                    selected_option_map[option_id]
                    for option_id in normalized_option_ids
                    if option_id in selected_option_map
                ]
        question_results.append({
            **score,
            "question_text": question.question_text if question else None,
            "student_answer": answer.answer_text if answer else None,
            "student_selected_options": student_selected_options,
            "correct_answer": (
                (question.expected_answer or question.model_answer_text)
                if question else None
            ),
            "correct_options": [item[0] for item in correct_options],
            "question_image_url": f"/results/sessions/{session.id}/questions/{question.id}/image/question" if question and question.question_image_data else None,
            "expected_answer_image_url": f"/results/sessions/{session.id}/questions/{question.id}/image/expected" if question and question.expected_answer_image_data else None,
            "student_answer_image_url": f"/results/sessions/{session.id}/questions/{question.id}/image/student" if answer and answer.image_data else None,
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
        **_exam_attribution(session, exam, db),
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
        "creator_name": db.query(User).filter(User.id == exam.created_by).first().full_name if db.query(User).filter(User.id == exam.created_by).first() else "Unknown",
        "total_students": len(rows),
        "results": [
            {
                "session_id": session.id,
                "student_id": student.id,
                "student_name": student.full_name,
                **_exam_attribution(session, exam, db),
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
                **_exam_attribution(session, exam, db),
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
