from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.auth import hash_password
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import AdminActivityLog, Exam, ExamAssignment, ExamSession, Result, User
from app.schemas import (
    AdminUserCreate,
    MessageResponse,
    UserResponse,
    UserRole,
    UserStatusUpdate,
)
from app.services.admin_service import (
    get_dashboard_statistics,
    record_admin_activity,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin Management"]
)

def _utc_iso(value):
    """Serialize database UTC timestamps with an explicit UTC offset."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.isoformat()


def _performance_grade(percentage):
    value = float(percentage or 0)
    if value >= 90:
        return "A+"
    if value >= 80:
        return "A"
    if value >= 70:
        return "B"
    if value >= 60:
        return "C"
    if value >= 50:
        return "D"
    return "F"


@router.get("/dashboard")
def admin_dashboard(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return platform statistics to authenticated Admins."""
    return get_dashboard_statistics(db)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_staff_account(
    user_data: AdminUserCreate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Allow Admins to create Admin and Examiner accounts."""

    if user_data.role not in (UserRole.ADMIN, UserRole.EXAMINER):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins can create only Admin or Examiner accounts."
        )

    normalized_email = str(user_data.email).strip().lower()

    existing_user = db.query(User).filter(
        func.lower(User.email) == normalized_email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    new_user = User(
        full_name=user_data.full_name.strip(),
        email=normalized_email,
        department=(
            user_data.department.strip()
            if user_data.department and user_data.department.strip()
            else None
        ),
        password_hash=hash_password(user_data.password),
        role=user_data.role.value,
        is_active=True
    )

    try:
        db.add(new_user)
        db.flush()

        record_admin_activity(
            db=db,
            actor_user_id=current_admin.id,
            target_user_id=new_user.id,
            action=(
                "examiner_created"
                if user_data.role == UserRole.EXAMINER
                else "admin_created"
            ),
            details={
                "email": normalized_email,
                "role": user_data.role.value,
                "department": new_user.department,
            },
        )

        db.commit()
        db.refresh(new_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    return new_user


@router.get(
    "/users",
    response_model=list[UserResponse]
)
def list_users(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Allow Admins to view all user accounts."""
    return db.query(User).order_by(User.id).all()


@router.get("/activity-logs")
def list_admin_activity_logs(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return the latest 100 Admin audit events."""

    actor = aliased(User)
    target = aliased(User)

    rows = (
        db.query(AdminActivityLog, actor, target)
        .join(actor, AdminActivityLog.actor_user_id == actor.id)
        .outerjoin(target, AdminActivityLog.target_user_id == target.id)
        .order_by(AdminActivityLog.created_at.desc(), AdminActivityLog.id.desc())
        .limit(100)
        .all()
    )

    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "actor_name": actor_user.full_name,
            "target_user_id": log.target_user_id,
            "target_name": target_user.full_name if target_user else None,
            "action": log.action,
            "details": log.details or {},
            "created_at": (
                log.created_at.isoformat()
                if isinstance(log.created_at, datetime)
                else None
            ),
        }
        for log, actor_user, target_user in rows
    ]


@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse
)
def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Allow Admins to delete accounts when no records depend on them."""

    target_user = db.query(User).filter(User.id == user_id).first()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found."
        )

    if target_user.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account."
        )

    if target_user.role not in (
        UserRole.STUDENT.value,
        UserRole.EXAMINER.value,
        UserRole.ADMIN.value
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account type cannot be deleted."
        )

    if target_user.role == UserRole.ADMIN.value and target_user.is_active:
        active_admin_count = db.query(User).filter(
            User.role == UserRole.ADMIN.value,
            User.is_active.is_(True)
        ).count()

        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active Admin account cannot be deleted."
            )

    deleted_user_details = {
        "email": target_user.email,
        "full_name": target_user.full_name,
        "role": target_user.role,
    }

    try:
        # Keep the audit record even though the target account is deleted.
        # target_user_id is intentionally NULL to avoid a dangling FK.
        record_admin_activity(
            db=db,
            actor_user_id=current_admin.id,
            target_user_id=None,
            action="user_deleted",
            details={
                "target_user_id": target_user.id,
                **deleted_user_details,
            },
        )
        db.delete(target_user)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This account is linked to existing examination or audit "
                "records and cannot be permanently deleted. Deactivate it "
                "instead."
            )
        )

    return MessageResponse(message="User account deleted successfully.")


@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse
)
def update_user_status(
    user_id: int,
    status_data: UserStatusUpdate,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """Allow Admins to activate or deactivate user accounts."""

    target_user = db.query(User).filter(User.id == user_id).first()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found."
        )

    if target_user.id == current_admin.id and not status_data.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account."
        )

    if (
        target_user.role == UserRole.ADMIN.value
        and target_user.is_active
        and not status_data.is_active
    ):
        active_admin_count = db.query(User).filter(
            User.role == UserRole.ADMIN.value,
            User.is_active.is_(True)
        ).count()

        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active Admin cannot be deactivated."
            )

    previous_status = bool(target_user.is_active)
    target_user.is_active = status_data.is_active

    try:
        if previous_status != status_data.is_active:
            record_admin_activity(
                db=db,
                actor_user_id=current_admin.id,
                target_user_id=target_user.id,
                action=(
                    "user_activated"
                    if status_data.is_active
                    else "user_deactivated"
                ),
                details={
                    "email": target_user.email,
                    "role": target_user.role,
                    "previous_status": previous_status,
                    "new_status": status_data.is_active,
                },
            )

        db.commit()
        db.refresh(target_user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Unable to update account status."
        )

    return target_user


@router.get("/examiners", response_model=list[UserResponse])
def list_examiners(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all Examiner accounts, including inactive accounts."""
    return db.query(User).filter(
        User.role == UserRole.EXAMINER.value
    ).order_by(User.full_name.asc()).all()


@router.get("/students", response_model=list[UserResponse])
def list_students(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all Student accounts, including inactive accounts."""
    return db.query(User).filter(
        User.role == UserRole.STUDENT.value
    ).order_by(User.full_name.asc()).all()


@router.get("/exams")
def list_all_examinations(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all exams with creator and session counts for Admin oversight."""
    rows = db.query(Exam, User).outerjoin(
        User, User.id == Exam.created_by
    ).order_by(Exam.id.desc()).all()
    return {
        "total": len(rows),
        "exams": [
            {
                "exam_id": exam.id,
                "title": exam.title,
                "subject": exam.subject,
                "created_by": exam.created_by,
                "creator_name": creator.full_name if creator else None,
                "duration_minutes": exam.duration_minutes,
                "total_questions": exam.total_questions,
                "start_time": _utc_iso(exam.start_time),
                "end_time": _utc_iso(exam.end_time),
                "session_count": db.query(ExamSession.id).filter(
                    ExamSession.exam_id == exam.id
                ).count(),
            }
            for exam, creator in rows
        ],
    }


@router.get("/performance")
def get_historical_student_performance(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return published historical performance across all examinations."""
    rows = db.query(Result, ExamSession, Exam, User).join(
        ExamSession, Result.session_id == ExamSession.id
    ).join(
        Exam, Exam.id == ExamSession.exam_id
    ).join(
        User, User.id == ExamSession.student_id
    ).filter(
        Result.is_published.is_(True)
    ).order_by(
        Result.published_at.desc(),
        Result.id.desc(),
    ).limit(2000).all()

    return {
        "total_published_results": len(rows),
        "performance": [
            {
                "result_id": result.id,
                "student_id": student.id,
                "student_name": student.full_name,
                "exam_id": exam.id,
                "exam_title": exam.title,
                "obtained_marks": result.obtained_marks,
                "total_marks": result.total_marks,
                "percentage": result.percentage,
                "grade": _performance_grade(result.percentage),
                "published_at": result.published_at,
            }
            for result, session, exam, student in rows
        ],
    }


@router.get("/schedules")
def list_all_exam_schedules(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all active student assignments with examination schedules."""
    StudentAccount = aliased(User)
    CreatorAccount = aliased(User)
    rows = db.query(
        ExamAssignment, Exam, StudentAccount, CreatorAccount
    ).join(
        Exam, Exam.id == ExamAssignment.exam_id
    ).join(
        StudentAccount, StudentAccount.id == ExamAssignment.student_id
    ).outerjoin(
        CreatorAccount, CreatorAccount.id == Exam.created_by
    ).filter(
        ExamAssignment.is_active.is_(True)
    ).order_by(
        Exam.start_time.asc(),
        Exam.title.asc(),
        StudentAccount.full_name.asc(),
    ).all()

    return {
        "total_assignments": len(rows),
        "schedules": [
            {
                "exam_id": exam.id,
                "exam_title": exam.title,
                "creator_id": exam.created_by,
                "creator_name": creator.full_name if creator else None,
                "student_id": student.id,
                "student_name": student.full_name,
                "student_email": student.email,
                "start_time": _utc_iso(exam.start_time),
                "end_time": _utc_iso(exam.end_time),
                "duration_minutes": exam.duration_minutes,
                "assigned_at": _utc_iso(assignment.assigned_at),
                "assigned_by": assignment.assigned_by,
            }
            for assignment, exam, student, creator in rows
        ],
    }
