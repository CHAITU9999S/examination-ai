
import json
from datetime import datetime

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import verify_token
from app.database import get_db
from app.models import (
    Answer,
    ExamSession,
    Option,
    QuestionBank,
    User,
)


router = APIRouter(
    prefix="/exam-sessions",
    tags=["Exam Answers"],
)

exam_token_scheme = HTTPBearer(auto_error=False)


# ==========================================
# ANSWER SUBMISSION SCHEMA
# ==========================================

class AnswerSubmission(BaseModel):
    answer_text: str = Field(
        min_length=1,
        max_length=50000,
    )


# ==========================================
# QUESTION TYPE HELPER
# ==========================================

def get_question_type_value(question) -> str:
    """Return the question type as a consistent string."""

    question_type = question.question_type

    return getattr(
        question_type,
        "value",
        question_type,
    )


# ==========================================
# EXAM TOKEN VALIDATION
# ==========================================

def validate_student_exam_token(
    credentials: HTTPAuthorizationCredentials,
    session_id: int,
    db: Session,
):
    """Validate exam token and its student/session identity."""

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Exam access token is required.",
        )

    payload = verify_token(
        credentials.credentials,
        expected_token_type="exam",
    )

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired exam access token.",
        )

    try:
        exam_id = int(payload.get("exam_id"))
        student_id = int(payload.get("student_id"))
        token_user_id = int(payload.get("sub"))
        token_session_id = int(payload.get("session_id"))

    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid exam token identity.",
        )

    if (
        student_id != token_user_id
        or session_id != token_session_id
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam token identity mismatch.",
        )

    student = db.query(User).filter(
        User.id == student_id,
    ).first()

    if (
        student is None
        or not student.is_active
        or student.role != "student"
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Student account is invalid or inactive.",
        )

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == student_id,
    ).first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )

    return session


# ==========================================
# ACTIVE SESSION VALIDATION
# ==========================================

def get_active_session_for_update(
    session_id: int,
    exam_id: int,
    student_id: int,
    db: Session,
):
    """Lock and retrieve an active exam session."""

    session = db.query(ExamSession).filter(
        ExamSession.id == session_id,
        ExamSession.exam_id == exam_id,
        ExamSession.student_id == student_id,
    ).with_for_update().first()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Exam session not found.",
        )

    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This exam session is no longer active.",
        )

    now = datetime.utcnow()

    if (
        session.expires_at is None
        or now >= session.expires_at
    ):
        try:
            session.status = "submitted"
            session.submitted_at = now
            db.commit()

        except SQLAlchemyError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Unable to finalize the expired exam session.",
            )

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Exam time has expired. "
                "Your exam session has been submitted."
            ),
        )

    return session


# ==========================================
# SESSION QUESTION VALIDATION
# ==========================================

def get_session_question_ids(session) -> set[int]:
    """Return the question IDs assigned to the session."""

    selected_ids = session.selected_question_ids

    if not isinstance(selected_ids, list) or not selected_ids:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The question paper has not been assigned to this session. "
                "Please contact the examiner."
            ),
        )

    if any(
        isinstance(question_id, bool)
        or not isinstance(question_id, int)
        for question_id in selected_ids
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The saved examination paper is invalid.",
        )

    if len(selected_ids) != len(set(selected_ids)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The saved examination paper contains duplicate questions.",
        )

    return set(selected_ids)


# ==========================================
# TEXT ANSWER VALIDATION
# ==========================================

def validate_text_answer(
    answer_text: str,
    question_type: str,
):
    """Validate text answer content and basic word limits."""

    words = answer_text.split()
    word_count = len(words)

    if word_count == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer cannot be empty.",
        )

    # Prevent unusually large submissions.
    if word_count > 10000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer exceeds the maximum allowed word count.",
        )

    # These are safety limits, not examiner-configured limits.
    # Exact per-question limits can be added through a reviewed
    # additive database migration in a later implementation.
    if question_type == "short_answer" and word_count > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Short answer exceeds 1000 words.",
        )


# ==========================================
# GET SAVED ANSWERS
# ==========================================

@router.get("/{session_id}/answers")
def get_saved_answers(
    session_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme,
    ),
    db: Session = Depends(get_db),
):
    """Return saved answers belonging to the authenticated session."""

    session = validate_student_exam_token(
        credentials,
        session_id,
        db,
    )

    if session.status != "in_progress":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Answers cannot be retrieved through an inactive exam session.",
        )

    if (
        session.expires_at is None
        or datetime.utcnow() >= session.expires_at
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Exam time has expired.",
        )

    answers = db.query(Answer).filter(
        Answer.session_id == session.id,
    ).order_by(
        Answer.question_id,
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
                "image_path": answer.image_path,
            }
            for answer in answers
        ],
    }


# ==========================================
# SAVE OR UPDATE EXAM ANSWER
# ==========================================

@router.post(
    "/{session_id}/answers/{question_id}",
    status_code=status.HTTP_200_OK,
)
def save_exam_answer(
    session_id: int,
    question_id: int,
    submission: AnswerSubmission,
    credentials: HTTPAuthorizationCredentials = Depends(
        exam_token_scheme,
    ),
    db: Session = Depends(get_db),
):
    """Save or update one answer in the authenticated exam session."""

    validated_session = validate_student_exam_token(
        credentials,
        session_id,
        db,
    )

    session = get_active_session_for_update(
        session_id=session_id,
        exam_id=validated_session.exam_id,
        student_id=validated_session.student_id,
        db=db,
    )

    selected_question_ids = get_session_question_ids(session)

    if question_id not in selected_question_ids:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This question does not belong to your examination paper.",
        )

    question = db.query(QuestionBank).filter(
        QuestionBank.id == question_id,
    ).first()

    if question is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Question not found.",
        )

    answer_text = submission.answer_text.strip()

    if not answer_text:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Answer cannot be empty.",
        )

    question_type = get_question_type_value(question)

    # --------------------------------------
    # MCQ VALIDATION
    # --------------------------------------

    if question_type == "MCQ":

        try:
            option_id = int(answer_text)

        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="For MCQ, submit the selected option ID.",
            )

        option = db.query(Option).filter(
            Option.id == option_id,
            Option.question_id == question_id,
        ).first()

        if option is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Selected option does not belong to this question.",
            )

        answer_text = str(option_id)

    # --------------------------------------
    # MULTI-SELECT VALIDATION
    # --------------------------------------

    elif question_type == "multi_select":

        try:
            option_ids = json.loads(answer_text)

        except (json.JSONDecodeError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "For multiple-select, submit a JSON array "
                    "of option IDs."
                ),
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
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Submit a non-empty array of unique option IDs.",
            )

        valid_options = db.query(Option.id).filter(
            Option.question_id == question_id,
            Option.id.in_(option_ids),
        ).all()

        valid_option_ids = {
            option.id for option in valid_options
        }

        if valid_option_ids != set(option_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "One or more selected options do not belong "
                    "to this question."
                ),
            )

        answer_text = json.dumps(option_ids)

    # --------------------------------------
    # SHORT AND LONG ANSWER VALIDATION
    # --------------------------------------

    elif question_type in (
        "short_answer",
        "long_answer",
    ):
        validate_text_answer(
            answer_text,
            question_type,
        )

    # --------------------------------------
    # IMAGE UPLOAD QUESTIONS
    # --------------------------------------

    elif question_type == "image_upload":

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Image upload answers must use the "
                "secure image upload endpoint."
            ),
        )

    else:

        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported question type.",
        )

    # ======================================
    # SAVE ANSWER
    # ======================================

    try:
        answer = db.query(Answer).filter(
            Answer.session_id == session_id,
            Answer.question_id == question_id,
        ).with_for_update().first()

        if answer is None:
            answer = Answer(
                session_id=session_id,
                question_id=question_id,
                answer_text=answer_text,
            )
            db.add(answer)

        else:
            answer.answer_text = answer_text

        db.commit()
        db.refresh(answer)

    except IntegrityError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The answer could not be saved because another "
                "submission changed this question at the same time. "
                "Please try again."
            ),
        )

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="A database error occurred while saving the answer.",
        )

    return {
        "message": "Answer saved successfully.",
        "answer_id": answer.id,
        "session_id": session_id,
        "question_id": question_id,
        "question_type": question_type,
        "saved": True,
    }
