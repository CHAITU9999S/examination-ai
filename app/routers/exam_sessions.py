
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Exam, ExamSession, QuestionBank, Option, User
from app.auth import create_exam_access_token, verify_token
from app.services.paper_generator import generate_paper

exam_token_scheme = HTTPBearer()

router = APIRouter(
    prefix="/exam-sessions",
    tags=["Exam Sessions"]
)


@router.post("/start/{exam_id}")
def start_exam(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    if current_user.role != "student":
        raise HTTPException(
            status_code=403,
            detail="Only students can start exams"
        )

    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    now = datetime.utcnow()

    if exam.start_time and now < exam.start_time:
        raise HTTPException(
            status_code=400,
            detail="Exam has not started yet"
        )

    if exam.end_time and now > exam.end_time:
        raise HTTPException(
            status_code=400,
            detail="Exam schedule has ended"
        )

    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == current_user.id,
        ExamSession.status == "in_progress"
    ).first()

    if not session:
        session = ExamSession(
            exam_id=exam_id,
            student_id=current_user.id
        )
        db.add(session)
        db.commit()
        db.refresh(session)

    exam_token = create_exam_access_token(
        exam_id=exam_id,
        student_id=current_user.id
    )

    return {
        "message": "Exam session started",
        "session_id": session.id,
        "exam_id": exam_id,
        "access_token": exam_token,
        "token_type": "bearer"
    }


@router.get("/paper/{exam_id}")
def get_exam_paper(
    exam_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(exam_token_scheme),
    db: Session = Depends(get_db)
):
    payload = verify_token(credentials.credentials)

    if not payload or payload.get("token_type") != "exam":
        raise HTTPException(
            status_code=401,
            detail="Invalid exam token"
        )

    try:
        token_exam_id = int(payload.get("exam_id"))
        student_id = int(payload.get("student_id"))
        token_user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid exam token identity"
        )

    if token_exam_id != exam_id:
        raise HTTPException(
            status_code=403,
            detail="Token does not belong to this exam"
        )

    if student_id != token_user_id:
        raise HTTPException(
            status_code=401,
            detail="Exam token identity mismatch"
        )

    student = db.query(User).filter(
        User.id == student_id
    ).first()

    if not student or not student.is_active or student.role != "student":
        raise HTTPException(
            status_code=403,
            detail="Student account is invalid or inactive"
        )

    session = db.query(ExamSession).filter(
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == student_id,
        ExamSession.status == "in_progress"
    ).first()

    if not session:
        raise HTTPException(
            status_code=403,
            detail="No active exam session"
        )

    exam = db.query(Exam).filter(
        Exam.id == exam_id
    ).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    query = db.query(QuestionBank).filter(
        QuestionBank.subject == exam.subject
    )

    rules = exam.selection_rules or {}

    if rules.get("difficulty"):
        query = query.filter(
            QuestionBank.difficulty == rules["difficulty"]
        )

    questions = query.order_by(QuestionBank.id).all()

    number = exam.total_questions or len(questions)

    question_ids = [question.id for question in questions]

    try:
        if exam.randomize_questions:
            selected_ids = generate_paper(
                question_ids,
                student_id,
                exam_id,
                number
            )
        else:
            if number <= 0 or number > len(question_ids):
                raise ValueError("Invalid number of questions")

            selected_ids = question_ids[:number]

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )

    question_map = {
        question.id: question
        for question in questions
    }

    paper = []

    for question_id in selected_ids:
        question = question_map[question_id]

        options = db.query(Option).filter(
            Option.question_id == question_id
        ).order_by(Option.id).all()

        paper.append({
            "question_id": question.id,
            "question_text": question.question_text,
            "question_type": question.question_type,
            "marks": question.marks,
            "negative_marks": question.negative_marks,
            "options": [
                {
                    "id": option.id,
                    "option_text": option.option_text
                }
                for option in options
            ]
        })

    return {
        "exam_id": exam_id,
        "session_id": session.id,
        "total_questions": len(paper),
        "questions": paper
    }
    
