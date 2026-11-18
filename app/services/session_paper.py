from sqlalchemy.orm import Session

from app.models import (
    Exam,
    ExamSession,
    QuestionBank
)
from app.services.paper_generator import generate_paper


def generate_session_question_ids(
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


def get_or_create_session_question_ids(
    session: ExamSession,
    exam: Exam,
    db: Session
):
    if session.selected_question_ids is not None:
        selected_ids = session.selected_question_ids

        if (
            not isinstance(selected_ids, list)
            or any(
                isinstance(question_id, bool)
                or not isinstance(question_id, int)
                for question_id in selected_ids
            )
            or len(selected_ids) != len(set(selected_ids))
        ):
            raise ValueError(
                "Saved exam question selection is invalid"
            )

        return selected_ids

    selected_ids = generate_session_question_ids(
        exam,
        session.student_id,
        db
    )

    session.selected_question_ids = selected_ids

    db.commit()
    db.refresh(session)

    return selected_ids
  
