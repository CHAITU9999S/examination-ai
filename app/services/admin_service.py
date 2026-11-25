from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import (
    AdminActivityLog,
    Exam,
    ExamSession,
    QuestionBank,
    User,
)


def record_admin_activity(
    db: Session,
    actor_user_id: int,
    action: str,
    target_user_id: Optional[int] = None,
    details: Optional[dict] = None,
):
    """
    Add an Admin audit event to the current transaction.

    The caller is responsible for committing the transaction.
    """
    activity = AdminActivityLog(
        actor_user_id=actor_user_id,
        target_user_id=target_user_id,
        action=action,
        details=details,
    )
    db.add(activity)
    return activity


def get_dashboard_statistics(db: Session):
    """
    Return account and examination statistics for the Admin dashboard.

    Accounts with a NULL is_active value are counted as inactive.
    """
    total_users = db.query(func.count(User.id)).filter(User.is_deleted.is_(False)).scalar() or 0
    total_students = (
        db.query(func.count(User.id))
        .filter(User.role == "student", User.is_deleted.is_(False))
        .scalar() or 0
    )
    total_examiners = (
        db.query(func.count(User.id))
        .filter(User.role == "examiner", User.is_deleted.is_(False))
        .scalar() or 0
    )
    total_admins = (
        db.query(func.count(User.id))
        .filter(User.role == "admin", User.is_deleted.is_(False))
        .scalar() or 0
    )
    active_users = (
        db.query(func.count(User.id))
        .filter(User.is_active.is_(True), User.is_deleted.is_(False))
        .scalar() or 0
    )
    inactive_users = (
        db.query(func.count(User.id))
        .filter(func.coalesce(User.is_active, False).is_(False), User.is_deleted.is_(False))
        .scalar() or 0
    )
    total_exams = db.query(func.count(Exam.id)).scalar() or 0
    total_questions = db.query(func.count(QuestionBank.id)).scalar() or 0
    total_sessions = db.query(func.count(ExamSession.id)).scalar() or 0

    return {
        "total_users": total_users,
        "total_students": total_students,
        "total_examiners": total_examiners,
        "total_admins": total_admins,
        "active_users": active_users,
        "inactive_users": inactive_users,
        "total_exams": total_exams,
        "total_questions": total_questions,
        "total_sessions": total_sessions,
        # Preserve the earlier service key for any existing callers.
        "total_exam_sessions": total_sessions,
    }
