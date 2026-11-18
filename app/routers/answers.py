import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.database import get_db
from app.models import (
    Answer,
    Exam,
    ExamSession,
    Option,
    QuestionBank,
    User
)
from app.services.paper_generator import generate_paper


router = APIRouter(
    prefix="/exam-sessions",
    tags=["Exam Answers"]
)

exam_token_scheme = HTTPBearer()


class AnswerSubmission(BaseModel):
    answer_text: str = Field(min_length=1)


def validate_student_exam_token(
    credentials: HTTPAuthorizationCredentials,
    session_id: int,
    db: Session
):
    payload = verify_token(credentials.credentials)

    if not payload or payload.get("token_type") != "exam":
        raise HTTPException(
            status_code=401,
            detail="Invalid exam access token"
        )

    try:
        exam_id = int(payload.get("exam_id"))
        student_id = int(payload.get("student_id"))
        token_user_id = int(payload.get("sub"))
        token_session_id = int(payload.get("session_id"))

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=401,
            detail="Invalid exam token identity"
        )

    if (
        student_id != token_user_id
        or session_id != token_session_id
    ):
        raise HTTPException(
            status_code=403,
            detail="Exam token identity mismatch"
        )

    student = db.query(User).filter(
        User.id == student_id
    ).first()

    if (
        not student
        or not student.is_active
        or student.role != "student"
    ):
        raise HTTPException(
            status_code=403,
            detail="Student account is invalid or inactive"
        )

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == student_id
    ).first()

    if not session:
        raise HTTPException(
            status_code=404,
            detail="Exam session not found"
        )

    return payload, session


def get_selected_question_ids(
    exam: Exam,
    student_id: int,
    db: Session
):
    query = db.query(QuestionBank).filter(
        QuestionBank.subject == exam.subject
    )

    rules = exam.selection_rules or {}

    if (
        rules.get("difficulty")
        and not rules.get("difficulty_counts")
    ):
        query = query.filter(
            QuestionBank.difficulty == rules["difficulty"]
        )

    questions = query.order_by(
        QuestionBank.id
    ).all()

    question_ids = [
        question.id for question in questions
    ]

    question_details = {
        question.id: {
            "difficulty": question.difficulty,
            "question_type": question.question_type
        }
        for question in questions
    }

    number = exam.total_questions or len(questions)

    try:
        return generate_paper(
            question_ids,
            student_id,
            exam.id,
            number,
            question_details=question_details,
            difficulty_counts=rules.get("difficulty_counts"),
            question_type_counts=rules.get("question_type_counts"),
            randomize=exam.randomize_questions
        )

    except ValueError as error:
        raise HTTPException(
            status_code=400,
            detail=str(error)
        )


@router.get("/{session_id}/answers")
def get_saved_answers(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db)
):

    payload, session = validate_student_exam_token(
        credentials,
        session_id,
        db
    )

    answers = db.query(Answer).filter(
        Answer.session_id == session.id
    ).order_by(
        Answer.question_id
    ).all()

    return {
        "session_id": session.id,
        "exam_id": session.exam_id,
        "status": session.status,
        "total_saved_answers": len(answers),
        "answers": [
            {
                "answer_id": answer.id,
                "question_id": answer.question_id,
                "answer_text": answer.answer_text,
                "image_path": answer.image_path
            }
            for answer in answers
        ]
    }


@router.post("/{session_id}/answers/{question_id}")
def save_exam_answer(
    session_id: int,
    question_id: int,
    submission: AnswerSubmission,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme
    ),
    db: Session = Depends(get_db)
):

    payload, session = validate_student_exam_token(
        credentials,
        session_id,
        db
    )

    if session.status != "in_progress":
        raise HTTPException(
            status_code=409,
            detail="This exam session is no longer active"
        )

    # Lock the session while saving an answer.
    session = db.query(ExamSession).filter(
        ExamSession.id == session_id
    ).with_for_update().first()

    if not session or session.status != "in_progress":
        raise HTTPException(
            status_code=409,
            detail="This exam session is no longer active"
        )

    now = datetime.utcnow()

    if now >= session.expires_at:
        session.status = "submitted"
        session.submitted_at = now
        db.commit()

        raise HTTPException(
            status_code=403,
            detail="Exam time has expired. Your exam has been submitted"
        )

    exam = db.query(Exam).filter(
        Exam.id == session.exam_id
    ).first()

    if not exam:
        raise HTTPException(
            status_code=404,
            detail="Exam not found"
        )

    selected_question_ids = get_selected_question_ids(
        exam,
        session.student_id,
        db
    )

    if question_id not in selected_question_ids:
        raise HTTPException(
            status_code=403,
            detail="This question does not belong to your exam paper"
        )

    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id
    ).first()

    if not question:
        raise HTTPException(
            status_code=404,
            detail="Question not found"
        )

    answer_text = submission.answer_text.strip()

    if not answer_text:
        raise HTTPException(
            status_code=400,
            detail="Answer cannot be empty"
        )

    # Validate MCQ answers.
    if question.question_type == "MCQ":

        try:
            option_id = int(answer_text)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="For MCQ, submit the selected option ID"
            )

        option = db.query(Option).filter(
            Option.id == option_id,
            Option.question_id == question_id
        ).first()

        if not option:
            raise HTTPException(
                status_code=400,
                detail="Selected option does not belong to this question"
            )

        answer_text = str(option_id)

    # Validate multiple-select answers.
    elif question.question_type == "multi_select":

        try:
            option_ids = json.loads(answer_text)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="For multiple-select, submit a JSON array of option IDs"
            )

        if (
            not isinstance(option_ids, list)
            or not option_ids
            or any(
                isinstance(option_id, bool)
                or not isinstance(option_id, int)
                for option_id in option_ids
            )
            or len(option_ids) != len(set(option_ids))
        ):
            raise HTTPException(
                status_code=400,
                detail="Submit a non-empty array of unique option IDs"
            )

        valid_options = db.query(Option.id).filter(
            Option.question_id == question_id,
            Option.id.in_(option_ids)
        ).all()

        valid_option_ids = {
            option.id for option in valid_options
        }

        if valid_option_ids != set(option_ids):
            raise HTTPException(
                status_code=400,
                detail="One or more selected options do not belong to this question"
            )

        answer_text = json.dumps(option_ids)

    elif question.question_type in (
        "short_answer",
        "long_answer"
    ):
        pass

    elif question.question_type == "image_upload":
        raise HTTPException(
            status_code=400,
            detail="Image upload answers require the separate secure upload endpoint"
        )

    else:
        raise HTTPException(
            status_code=400,
            detail="Unsupported question type"
        )

    # Update an existing answer or create a new one.
    answer = db.query(Answer).filter(
        Answer.session_id == session_id,
        Answer.question_id == question_id
    ).first()

    if answer:
        answer.answer_text = answer_text
        answer.image_path = None

    else:
        answer = Answer(
            session_id=session_id,
            question_id=question_id,
            answer_text=answer_text
        )
        db.add(answer)

    db.commit()
    db.refresh(answer)

    return {
        "message": "Answer saved successfully",
        "answer_id": answer.id,
        "session_id": session_id,
        "question_id": question_id,
        "question_type": question.question_type,
        "saved": True
    }
    
