import math


from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError

from app.models import (
    Exam,
    ExamQuestion,
    ExamSession,
    QuestionBank,
)
from app.services.paper_generator import generate_paper


# ==========================================
# HELPER FUNCTIONS
# ==========================================

def _enum_value(value):
    """Convert an enum value to its underlying string."""

    return getattr(value, "value", value)


def _get_assigned_questions(
    exam: Exam,
    db: Session,
):
    """
    Retrieve only questions assigned to this examination.

    ExamQuestion is the authoritative assignment table.
    """

    questions = (
        db.query(QuestionBank)
        .join(
            ExamQuestion,
            ExamQuestion.question_id == QuestionBank.id,
        )
        .filter(
            ExamQuestion.exam_id == exam.id,
        )
        .order_by(
            ExamQuestion.question_order.asc(),
            ExamQuestion.id.asc(),
        )
        .all()
    )

    if not questions:
        raise ValueError(
            "No questions have been assigned to this examination."
        )

    return questions


def _get_question_count(
    exam: Exam,
    available_count: int,
):
    """Determine the number of questions required for the paper."""

    number = exam.total_questions

    if number is None:
        number = available_count

    if (
        isinstance(number, bool)
        or not isinstance(number, int)
        or number <= 0
    ):
        raise ValueError(
            "The examination must have a positive question count."
        )

    if number > available_count:
        raise ValueError(
            "Not enough assigned questions are available for this examination."
        )

    return number


def _get_selection_question_pool(
    exam: Exam,
    questions: list[QuestionBank],
):
    """Apply simple exam-wide selection filters consistently."""

    rules = exam.selection_rules or {}

    if not isinstance(rules, dict):
        raise ValueError(
            "Examination selection rules must be a dictionary."
        )

    if (
        rules.get("difficulty")
        and not rules.get("difficulty_counts")
        and not rules.get("question_type_counts")
    ):
        required_difficulty = rules["difficulty"]

        questions = [
            question
            for question in questions
            if _enum_value(question.difficulty) == required_difficulty
        ]

        if not questions:
            raise ValueError(
                "No assigned questions match the configured difficulty."
            )

    return questions


# ==========================================
# GENERATE SESSION QUESTION IDS
# ==========================================

def generate_session_question_ids(
    exam: Exam,
    student_id: int,
    db: Session,
):
    """
    Generate a deterministic question paper for one student.

    The same student and examination receive the same selection
    when the same available questions and configuration are used.
    """

    if not isinstance(student_id, int) or isinstance(student_id, bool):
        raise ValueError("Student ID must be a valid integer.")

    if student_id <= 0:
        raise ValueError("Student ID must be positive.")

    questions = _get_assigned_questions(
        exam,
        db,
    )

    if exam.subject and any(
        (question.subject or "").casefold() != exam.subject.casefold()
        for question in questions
    ):
        raise ValueError(
            "Every question in the examination bank must match the examination subject."
        )

    # Enforce one maximum-mark value for each type/difficulty group
    # at paper-generation time, not only in the creator interface.
    marks_by_group = {}
    for question in questions:
        group = (
            _enum_value(question.question_type),
            _enum_value(question.difficulty),
        )
        marks = float(question.marks or 0)
        if group in marks_by_group and not math.isclose(
            marks_by_group[group], marks, rel_tol=0, abs_tol=0.0001
        ):
            raise ValueError(
                "Maximum marks must be equal within each question type and difficulty group."
            )
        marks_by_group[group] = marks

    rules = exam.selection_rules or {}

    if not isinstance(rules, dict):
        raise ValueError(
            "Examination selection rules must be a dictionary."
        )

    questions = _get_selection_question_pool(
        exam,
        questions,
    )

    question_count = _get_question_count(
        exam,
        len(questions),
    )

    question_ids = [
        question.id
        for question in questions
    ]

    question_details = {
        question.id: {
            "difficulty": _enum_value(question.difficulty),
            "question_type": _enum_value(question.question_type),
        }
        for question in questions
    }

    difficulty_counts = rules.get("difficulty_counts")
    question_type_counts = rules.get("question_type_counts")

    # Give each student a different question set whenever the pool allows it.
    # When question-order randomization is disabled, retain the exam's configured
    # order within each student's unique selection.
    previous_selections = db.query(
        ExamSession.selected_question_ids,
    ).filter(
        ExamSession.exam_id == exam.id,
        ExamSession.selected_question_ids.isnot(None),
    ).all()

    used_papers = {
        frozenset(selection[0])
        for selection in previous_selections
        if isinstance(selection[0], list)
        and len(selection[0]) == question_count
    }

    group_counts = rules.get("group_counts")
    total_combinations = math.comb(len(question_ids), question_count)
    if group_counts:
        available_by_group = {}
        for question_id in question_ids:
            details = question_details.get(question_id) or {}
            difficulty = _enum_value(details.get("difficulty"))
            question_type = _enum_value(details.get("question_type"))
            key = f"{difficulty}|{question_type}"
            available_by_group[key] = available_by_group.get(key, 0) + 1
        total_combinations = 1
        for group, required in group_counts.items():
            total_combinations *= math.comb(
                available_by_group.get(group, 0),
                required,
            )

    selected_ids = None
    # Try many deterministic seeds to find an unused valid paper.
    for seed_salt in range(10000):
        candidate = generate_paper(
            question_ids=question_ids,
            student_id=student_id,
            exam_id=exam.id,
            number_of_questions=question_count,
            question_details=question_details,
            difficulty_counts=difficulty_counts,
            question_type_counts=question_type_counts,
            group_counts=group_counts,
            randomize=True,
            seed_salt=seed_salt,
        )
        if frozenset(candidate) not in used_papers:
            selected_ids = candidate
            break

    if selected_ids is None:
        # All valid combinations have been used (or the deterministic search
        # could not find another). Do not block an otherwise eligible student.
        selected_ids = generate_paper(
            question_ids=question_ids,
            student_id=student_id,
            exam_id=exam.id,
            number_of_questions=question_count,
            question_details=question_details,
            difficulty_counts=difficulty_counts,
            question_type_counts=question_type_counts,
            group_counts=group_counts,
            randomize=True,
            seed_salt=10000,
        )

    if not exam.randomize_questions:
        question_order = {question_id: index for index, question_id in enumerate(question_ids)}
        selected_ids.sort(key=lambda question_id: question_order[question_id])

    if len(selected_ids) != question_count:
        raise ValueError(
            "Generated question count does not match the examination configuration."
        )

    return selected_ids


# ==========================================
# GET OR CREATE SAVED SESSION QUESTION IDS
# ==========================================

def get_or_create_session_question_ids(
    session: ExamSession,
    exam: Exam,
    db: Session,
):
    """
    Return the saved question selection for a session.

    If no selection exists, generate it once and save it.

    Reconnecting to an existing session must never generate
    a different question paper.
    """

    if session.exam_id != exam.id:
        raise ValueError(
            "The examination does not match the session."
        )

    if session.student_id <= 0:
        raise ValueError(
            "Invalid student ID in examination session."
        )

    try:
        assigned_questions = _get_assigned_questions(
            exam,
            db,
        )

        selection_pool = _get_selection_question_pool(
            exam,
            assigned_questions,
        )

        selection_pool_ids = {
            question.id
            for question in selection_pool
        }

        expected_count = _get_question_count(
            exam,
            len(selection_pool_ids),
        )

        saved_ids = session.selected_question_ids

        # Reuse an existing selection.
        if saved_ids is not None:

            if not isinstance(saved_ids, list):
                raise ValueError(
                    "Saved session question selection is invalid."
                )

            if any(
                isinstance(question_id, bool)
                or not isinstance(question_id, int)
                for question_id in saved_ids
            ):
                raise ValueError(
                    "Saved question IDs must be integers."
                )

            if len(saved_ids) != len(set(saved_ids)):
                raise ValueError(
                    "Saved session contains duplicate question IDs."
                )

            if len(saved_ids) != expected_count:
                raise ValueError(
                    "Saved question selection does not match "
                    "the examination question count."
                )

            if not set(saved_ids).issubset(selection_pool_ids):
                raise ValueError(
                    "Saved session contains questions outside the "
                    "configured examination selection."
                )

            return saved_ids

        # Generate a selection only when no saved selection exists.
        selected_ids = generate_session_question_ids(
            exam=exam,
            student_id=session.student_id,
            db=db,
        )

        if len(selected_ids) != expected_count:
            raise ValueError(
                "Generated question selection has an invalid count."
            )

        # Save the selection for future reconnects.
        session.selected_question_ids = selected_ids

        db.commit()
        db.refresh(session)

        return session.selected_question_ids

    except (ValueError, TypeError):
        db.rollback()
        raise

    except SQLAlchemyError:
        db.rollback()
        raise
