from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.auth import hash_password
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import (
    AdminActivityLog, Answer, AnswerMarkRevision, Exam, ExamAssignment,
    ExamConfigurationRevision, ExamQuestion, ExamQuestionMarksRevision,
    ExamSession, Option, PlatformSetting, ProctorEvent, QuestionBank, Result, User,
)
from app.question_bank_models import QuestionCollection, QuestionCollectionItem
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
    return db.query(User).filter(User.is_deleted.is_(False)).order_by(User.id).all()


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
        .filter(actor.role == UserRole.ADMIN.value)
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


@router.get("/examiner-activity-logs")
def list_examiner_activity_logs(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return recent examination and question-bank actions performed by Examiners."""
    actor = aliased(User)
    rows = (
        db.query(AdminActivityLog, actor)
        .join(actor, AdminActivityLog.actor_user_id == actor.id)
        .filter(
            actor.role == UserRole.EXAMINER.value,
            or_(
                AdminActivityLog.action.like("exam%"),
                AdminActivityLog.action.like("examination%"),
                AdminActivityLog.action.like("question_bank%"),
                AdminActivityLog.action.like("question_%"),
            ),
        )
        .order_by(AdminActivityLog.created_at.desc(), AdminActivityLog.id.desc())
        .limit(200)
        .all()
    )
    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "actor_name": actor_user.full_name,
            "action": log.action,
            "details": log.details or {},
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log, actor_user in rows
    ]


def _session_is_completed(db: Session, session: ExamSession) -> bool:
    return (
        session.status in {
            "submitted", "auto_submitted", "expired", "completed"
        }
        or session.submitted_at is not None
        or db.query(Result.id).filter(Result.session_id == session.id).first() is not None
    )


def _delete_session_history(db: Session, session_ids: list[int]) -> None:
    if not session_ids:
        return
    answer_ids = [
        row[0] for row in db.query(Answer.id).filter(
            Answer.session_id.in_(session_ids)
        ).all()
    ]
    if answer_ids:
        db.query(AnswerMarkRevision).filter(
            AnswerMarkRevision.answer_id.in_(answer_ids)
        ).delete(synchronize_session=False)
    db.query(Result).filter(Result.session_id.in_(session_ids)).delete(
        synchronize_session=False
    )
    db.query(ProctorEvent).filter(ProctorEvent.session_id.in_(session_ids)).delete(
        synchronize_session=False
    )
    db.query(Answer).filter(Answer.session_id.in_(session_ids)).delete(
        synchronize_session=False
    )
    db.query(ExamSession).filter(ExamSession.id.in_(session_ids)).delete(
        synchronize_session=False
    )


def _delete_exam_and_history(db: Session, exam_id: int) -> None:
    question_ids = [
        row[0] for row in db.query(ExamQuestion.question_id).filter(
            ExamQuestion.exam_id == exam_id
        ).all()
    ]
    session_ids = [
        row[0] for row in db.query(ExamSession.id).filter(
            ExamSession.exam_id == exam_id
        ).all()
    ]
    _delete_session_history(db, session_ids)
    db.query(ExamAssignment).filter(ExamAssignment.exam_id == exam_id).delete(
        synchronize_session=False
    )
    db.query(ExamConfigurationRevision).filter(
        ExamConfigurationRevision.exam_id == exam_id
    ).delete(synchronize_session=False)
    db.query(ExamQuestionMarksRevision).filter(
        ExamQuestionMarksRevision.exam_id == exam_id
    ).delete(synchronize_session=False)
    db.query(ExamQuestion).filter(ExamQuestion.exam_id == exam_id).delete(
        synchronize_session=False
    )
    db.query(Exam).filter(Exam.id == exam_id).delete(synchronize_session=False)

    # Remove only detached questions that have no remaining use anywhere.
    for question_id in question_ids:
        still_used = any((
            db.query(ExamQuestion.id).filter(
                ExamQuestion.question_id == question_id
            ).first(),
            db.query(Answer.id).filter(
                Answer.question_id == question_id
            ).first(),
            db.query(QuestionCollectionItem.id).filter(
                QuestionCollectionItem.question_id == question_id
            ).first(),
            db.query(QuestionBank.id).filter(
                QuestionBank.source_question_id == question_id
            ).first(),
        ))
        question = db.query(QuestionBank).filter(
            QuestionBank.id == question_id,
            QuestionBank.created_by.is_(None),
        ).first()
        if question is not None and not still_used:
            db.query(Option).filter(
                Option.question_id == question_id
            ).delete(synchronize_session=False)
            db.delete(question)


def _anonymize_deleted_account(user: User) -> None:
    user.full_name = f"Deleted {user.role.title()} #{user.id}"
    user.email = f"deleted-user-{user.id}@deleted.invalid"
    user.department = None
    user.password_hash = hash_password(secrets.token_urlsafe(40))
    user.is_active = False
    user.is_deleted = True
    user.active_session_id = None
    user.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)


def _delete_account_preserving_history(
    user_id: int,
    current_admin: User,
    db: Session,
    expected_role: str | None = None,
) -> MessageResponse:
    target = db.query(User).filter(
        User.id == user_id,
        User.is_deleted.is_(False),
    ).first()
    if target is None:
        raise HTTPException(status_code=404, detail="User account not found.")
    if target.id == current_admin.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")
    if expected_role and target.role != expected_role:
        raise HTTPException(status_code=404, detail="User account not found.")
    if target.role not in {
        UserRole.STUDENT.value, UserRole.EXAMINER.value, UserRole.ADMIN.value
    }:
        raise HTTPException(status_code=400, detail="This account type cannot be deleted.")
    if target.role == UserRole.ADMIN.value and target.is_active:
        active_admins = db.query(User.id).filter(
            User.role == UserRole.ADMIN.value,
            User.is_active.is_(True),
            User.is_deleted.is_(False),
        ).count()
        if active_admins <= 1:
            raise HTTPException(
                status_code=400,
                detail="The last active Admin account cannot be deleted.",
            )

    original = {
        "target_user_id": target.id,
        "role": target.role,
    }
    try:
        # Completed attempts remain available as historical records. Unfinished
        # attempts and future assignments are removed.
        own_sessions = db.query(ExamSession).filter(
            ExamSession.student_id == target.id
        ).all()
        completed_student_sessions = [
            item.id for item in own_sessions if _session_is_completed(db, item)
        ]
        unfinished_student_sessions = [
            item.id for item in own_sessions if not _session_is_completed(db, item)
        ]
        _delete_session_history(db, unfinished_student_sessions)

        retained_exam_ids: list[int] = []
        deleted_exam_ids: list[int] = []
        if target.role in {UserRole.ADMIN.value, UserRole.EXAMINER.value}:
            owned_exam_ids = [
                row[0] for row in db.query(Exam.id).filter(
                    Exam.created_by == target.id
                ).all()
            ]
            for exam_id in owned_exam_ids:
                exam_sessions = db.query(ExamSession).filter(
                    ExamSession.exam_id == exam_id
                ).all()
                completed = [
                    item.id for item in exam_sessions
                    if _session_is_completed(db, item)
                ]
                unfinished = [
                    item.id for item in exam_sessions
                    if not _session_is_completed(db, item)
                ]
                _delete_session_history(db, unfinished)
                if completed:
                    retained_exam_ids.append(exam_id)
                    # The examination is now historical, not scheduled.
                    db.query(ExamAssignment).filter(
                        ExamAssignment.exam_id == exam_id
                    ).delete(synchronize_session=False)
                else:
                    deleted_exam_ids.append(exam_id)
                    _delete_exam_and_history(db, exam_id)

            # Remove the deleted staff member's named banks. Keep question
            # records only when retained exams, completed answers, another
            # collection, or a copied question still depends on them.
            collection_ids = [
                row[0] for row in db.query(QuestionCollection.id).filter(
                    QuestionCollection.created_by == target.id
                ).all()
            ]
            if collection_ids:
                db.query(QuestionCollectionItem).filter(
                    QuestionCollectionItem.collection_id.in_(collection_ids)
                ).delete(synchronize_session=False)
                db.query(QuestionCollection).filter(
                    QuestionCollection.id.in_(collection_ids)
                ).delete(synchronize_session=False)

            owned_question_ids = [
                row[0] for row in db.query(QuestionBank.id).filter(
                    QuestionBank.created_by == target.id
                ).all()
            ]
            for question_id in owned_question_ids:
                used = any((
                    db.query(ExamQuestion.id).filter(
                        ExamQuestion.question_id == question_id
                    ).first(),
                    db.query(Answer.id).filter(
                        Answer.question_id == question_id
                    ).first(),
                    db.query(QuestionCollectionItem.id).filter(
                        QuestionCollectionItem.question_id == question_id
                    ).first(),
                    db.query(QuestionBank.id).filter(
                        QuestionBank.source_question_id == question_id
                    ).first(),
                ))
                question = db.query(QuestionBank).filter(
                    QuestionBank.id == question_id
                ).first()
                if question is None:
                    continue
                if used:
                    # Keep ownership attribution on the deleted-account tombstone.
                    # Retained questions appear in Admin > Retained Data.
                    pass
                else:
                    db.query(Option).filter(
                        Option.question_id == question_id
                    ).delete(synchronize_session=False)
                    db.delete(question)

        # Remove assignments involving this account. Revision history and
        # Admin activity logs are intentionally retained for later review.
        db.query(ExamAssignment).filter(
            or_(
                ExamAssignment.student_id == target.id,
                ExamAssignment.assigned_by == target.id,
            )
        ).delete(synchronize_session=False)

        _anonymize_deleted_account(target)
        record_admin_activity(
            db=db,
            actor_user_id=current_admin.id,
            target_user_id=target.id,
            action="user_account_deleted",
            details={
                **original,
                "retained_completed_exam_ids": retained_exam_ids,
                "retained_completed_submission_ids": completed_student_sessions,
                "deleted_unfinished_submission_count": len(unfinished_student_sessions),
                "deleted_exam_ids": deleted_exam_ids,
                "note": "Account anonymized; retained history can be reviewed and deleted separately.",
            },
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="The account could not be deleted safely. No changes were saved.",
        )

    retained_count = len(retained_exam_ids) + len(completed_student_sessions)
    return MessageResponse(
        message=(
            f"{target.role.title()} account deleted and anonymized. "
            f"{retained_count} completed examination record(s) retained. "
            "The Admin can review and delete retained records later from Retained Data."
        )
    )


@router.delete("/users/{user_id}/with-records", response_model=MessageResponse)
@router.delete("/users/{user_id}", response_model=MessageResponse)
def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _delete_account_preserving_history(user_id, current_admin, db)


@router.delete("/examiners/{user_id}/with-records", response_model=MessageResponse)
def delete_examiner_with_records(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _delete_account_preserving_history(
        user_id, current_admin, db, expected_role=UserRole.EXAMINER.value
    )


@router.delete("/admins/{user_id}/with-records", response_model=MessageResponse)
def delete_admin_with_records(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    return _delete_account_preserving_history(
        user_id, current_admin, db, expected_role=UserRole.ADMIN.value
    )


@router.get("/retained-data")
def list_retained_data(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """List completed records retained after Admin account deletion."""
    deleted_users = db.query(User).filter(
        User.is_deleted.is_(True)
    ).order_by(User.deleted_at.desc()).all()
    items = []
    seen_activity_ids = set()

    for deleted_user in deleted_users:
        if deleted_user.role in {UserRole.ADMIN.value, UserRole.EXAMINER.value}:
            exams = db.query(Exam).filter(
                Exam.created_by == deleted_user.id
            ).order_by(Exam.id.desc()).all()
            for exam in exams:
                completed_count = sum(
                    1 for session in db.query(ExamSession).filter(
                        ExamSession.exam_id == exam.id
                    ).all() if _session_is_completed(db, session)
                )
                if completed_count:
                    items.append({
                        "kind": "completed_exam",
                        "id": exam.id,
                        "title": exam.title,
                        "owner_id": deleted_user.id,
                        "owner_name": deleted_user.full_name,
                        "owner_role": deleted_user.role,
                        "description": f"{completed_count} completed student attempt(s)",
                    })

        sessions = db.query(ExamSession, Exam).join(
            Exam, Exam.id == ExamSession.exam_id
        ).filter(
            ExamSession.student_id == deleted_user.id
        ).order_by(ExamSession.id.desc()).all()
        for session, exam in sessions:
            if _session_is_completed(db, session):
                items.append({
                    "kind": "completed_submission",
                    "id": session.id,
                    "title": exam.title,
                    "owner_id": deleted_user.id,
                    "owner_name": deleted_user.full_name,
                    "owner_role": deleted_user.role,
                    "description": f"Completed student submission (session #{session.id})",
                })

        if deleted_user.role in {UserRole.ADMIN.value, UserRole.EXAMINER.value}:
            retained_questions = db.query(QuestionBank).filter(
                QuestionBank.created_by == deleted_user.id
            ).order_by(QuestionBank.id.desc()).all()
            for question in retained_questions:
                items.append({
                    "kind": "retained_question",
                    "id": question.id,
                    "title": question.question_text[:120],
                    "owner_id": deleted_user.id,
                    "owner_name": deleted_user.full_name,
                    "owner_role": deleted_user.role,
                    "description": "Question retained because examination or answer records still reference it. It can be deleted after those references are removed.",
                })

        activity_rows = db.query(AdminActivityLog).filter(
            or_(
                AdminActivityLog.actor_user_id == deleted_user.id,
                AdminActivityLog.target_user_id == deleted_user.id,
            )
        ).order_by(AdminActivityLog.id.desc()).all()
        for activity in activity_rows:
            if activity.id in seen_activity_ids:
                continue
            seen_activity_ids.add(activity.id)
            items.append({
                "kind": "admin_activity_log",
                "id": activity.id,
                "title": f"Admin activity: {activity.action}",
                "owner_id": deleted_user.id,
                "owner_name": deleted_user.full_name,
                "owner_role": deleted_user.role,
                "description": "Audit entry linked to this deleted account",
            })

        for revision_model, kind, label in (
            (ExamConfigurationRevision, "exam_configuration_revision", "Examination configuration history"),
            (ExamQuestionMarksRevision, "exam_question_marks_revision", "Question-paper marks history"),
            (AnswerMarkRevision, "answer_mark_revision", "Answer grading history"),
        ):
            revisions = db.query(revision_model).filter(
                revision_model.changed_by == deleted_user.id
                if revision_model is not AnswerMarkRevision
                else revision_model.revised_by == deleted_user.id
            ).all()
            for revision in revisions:
                items.append({
                    "kind": kind,
                    "id": revision.id,
                    "title": label,
                    "owner_id": deleted_user.id,
                    "owner_name": deleted_user.full_name,
                    "owner_role": deleted_user.role,
                    "description": f"Retained revision #{revision.id}",
                })

    return {"total": len(items), "items": items}


@router.delete("/retained-data/{kind}/{record_id}", response_model=MessageResponse)
def delete_retained_data(
    kind: str,
    record_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete one retained historical property only after explicit Admin action."""
    try:
        if kind == "completed_exam":
            exam = db.query(Exam).join(
                User, User.id == Exam.created_by
            ).filter(
                Exam.id == record_id,
                User.is_deleted.is_(True),
            ).first()
            if exam is None:
                raise HTTPException(status_code=404, detail="Retained examination not found.")
            if not any(
                _session_is_completed(db, session)
                for session in db.query(ExamSession).filter(
                    ExamSession.exam_id == exam.id
                ).all()
            ):
                raise HTTPException(status_code=409, detail="This examination is no longer retained as completed.")
            _delete_exam_and_history(db, exam.id)

        elif kind == "completed_submission":
            session = db.query(ExamSession).join(
                User, User.id == ExamSession.student_id
            ).filter(
                ExamSession.id == record_id,
                User.is_deleted.is_(True),
            ).first()
            if session is None or not _session_is_completed(db, session):
                raise HTTPException(status_code=404, detail="Retained submission not found.")
            _delete_session_history(db, [session.id])

        elif kind == "admin_activity_log":
            activity = db.query(AdminActivityLog).join(
                User,
                or_(
                    AdminActivityLog.actor_user_id == User.id,
                    AdminActivityLog.target_user_id == User.id,
                ),
            ).filter(
                AdminActivityLog.id == record_id,
                User.is_deleted.is_(True),
            ).first()
            if activity is None:
                raise HTTPException(status_code=404, detail="Retained activity log not found.")
            db.delete(activity)

        elif kind == "retained_question":
            question = db.query(QuestionBank).filter(
                QuestionBank.id == record_id,
                QuestionBank.creator.has(User.is_deleted.is_(True)),
            ).first()
            if question is None:
                raise HTTPException(status_code=404, detail="Retained question not found.")
            still_used = any((
                db.query(ExamQuestion.id).filter(
                    ExamQuestion.question_id == question.id
                ).first(),
                db.query(Answer.id).filter(
                    Answer.question_id == question.id
                ).first(),
                db.query(QuestionCollectionItem.id).filter(
                    QuestionCollectionItem.question_id == question.id
                ).first(),
                db.query(QuestionBank.id).filter(
                    QuestionBank.source_question_id == question.id
                ).first(),
            ))
            if still_used:
                raise HTTPException(
                    status_code=409,
                    detail="This question is still used by another examination, answer, or question bank. Delete those records first, then try again.",
                )
            db.query(Option).filter(
                Option.question_id == question.id
            ).delete(synchronize_session=False)
            db.delete(question)

        elif kind in {
            "exam_configuration_revision",
            "exam_question_marks_revision",
            "answer_mark_revision",
        }:
            revision_model, actor_field = {
                "exam_configuration_revision": (ExamConfigurationRevision, "changed_by"),
                "exam_question_marks_revision": (ExamQuestionMarksRevision, "changed_by"),
                "answer_mark_revision": (AnswerMarkRevision, "revised_by"),
            }[kind]
            revision = db.query(revision_model).filter(
                revision_model.id == record_id
            ).first()
            if revision is None:
                raise HTTPException(status_code=404, detail="Retained history record not found.")
            actor_id = getattr(revision, actor_field)
            actor = db.query(User).filter(
                User.id == actor_id,
                User.is_deleted.is_(True),
            ).first()
            if actor is None:
                raise HTTPException(status_code=404, detail="Retained history record not found.")
            db.delete(revision)
        else:
            raise HTTPException(status_code=400, detail="Unsupported retained record type.")

        record_admin_activity(
            db=db,
            actor_user_id=current_admin.id,
            target_user_id=None,
            action="retained_record_deleted",
            details={"kind": kind, "record_id": record_id},
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail="This retained record is still referenced by other data and cannot be deleted safely.",
        )

    return MessageResponse(message="Retained record deleted successfully.")


@router.get("/questions/reset-status")
def get_all_questions_reset_status(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Report whether the one-time global question deletion is still available."""
    setting = db.query(PlatformSetting).filter(
        PlatformSetting.setting_key == "all_questions_deleted_once",
    ).first()
    used = bool(setting and setting.setting_value == "true")
    available = setting is not None and not used
    return {
        "available": available,
        "used": used,
        "message": (
            "The database migration for the one-time question deletion has not been applied."
            if setting is None else
            "The one-time question deletion has already been used."
            if used else
            "The one-time question deletion is available to an Admin."
        ),
    }


@router.delete("/questions/all", response_model=MessageResponse)
def delete_all_questions_once(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete every question and dependent answer row exactly once."""
    try:
        setting = db.query(PlatformSetting).filter(
            PlatformSetting.setting_key == "all_questions_deleted_once",
        ).with_for_update().first()
        if setting is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The one-time deletion setting is not initialized. Apply the platform settings migration first.",
            )
        if setting.setting_value == "true":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The one-time deletion of all questions has already been used.",
            )

        # Lock the Admin rows as an additional serialization guard. The setting
        # row lock is the primary cross-Admin concurrency protection.
        db.query(User.id).filter(
            User.role == UserRole.ADMIN.value,
        ).order_by(User.id).with_for_update().all()

        question_ids = [row[0] for row in db.query(QuestionBank.id).all()]
        answer_ids = [row[0] for row in db.query(Answer.id).all()]

        if answer_ids:
            db.query(AnswerMarkRevision).filter(
                AnswerMarkRevision.answer_id.in_(answer_ids),
            ).delete(synchronize_session=False)
            db.query(Answer).filter(
                Answer.id.in_(answer_ids),
            ).delete(synchronize_session=False)

        # Keep examination sessions and Result snapshots, but remove the
        # question-dependent paper and answer rows that prevent question deletion.
        db.query(ExamQuestion).delete(synchronize_session=False)
        db.query(QuestionCollectionItem).delete(synchronize_session=False)
        if question_ids:
            db.query(QuestionBank).filter(
                QuestionBank.id.in_(question_ids),
            ).update(
                {QuestionBank.source_question_id: None},
                synchronize_session=False,
            )
            db.query(Option).filter(
                Option.question_id.in_(question_ids),
            ).delete(synchronize_session=False)
            db.query(QuestionBank).filter(
                QuestionBank.id.in_(question_ids),
            ).delete(synchronize_session=False)

        setting.setting_value = "true"
        setting.updated_by = current_admin.id
        setting.updated_at = datetime.utcnow()
        record_admin_activity(
            db=db,
            actor_user_id=current_admin.id,
            target_user_id=None,
            action="all_questions_deleted_once",
            details={
                "deleted_questions": len(question_ids),
                "deleted_answers": len(answer_ids),
                "deleted_exam_question_links": True,
                "exam_sessions_and_result_snapshots_preserved": True,
            },
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    return MessageResponse(
        message=(
            f"Deleted {len(question_ids)} questions and {len(answer_ids)} dependent answers. "
            "Examinations, sessions, and existing result snapshots were retained. "
            "This one-time action is now permanently disabled."
        )
    )


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

    target_user = db.query(User).filter(
        User.id == user_id,
        User.is_deleted.is_(False),
    ).first()

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
            User.is_active.is_(True),
            User.is_deleted.is_(False),
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
        User.role == UserRole.EXAMINER.value,
        User.is_deleted.is_(False),
    ).order_by(User.full_name.asc()).all()


@router.get("/students", response_model=list[UserResponse])
def list_students(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Return all Student accounts, including inactive accounts."""
    return db.query(User).filter(
        User.role == UserRole.STUDENT.value,
        User.is_deleted.is_(False),
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

@router.delete(
    "/users/{user_id}/with-records",
    response_model=MessageResponse,
)
def delete_user_with_records(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete a Student, Examiner, or Admin with the records for that role."""

    target_user = db.query(User).filter(User.id == user_id).first()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found.",
        )

    if target_user.role == UserRole.STUDENT.value:
        return delete_user(user_id, current_admin, db)

    if target_user.role == UserRole.EXAMINER.value:
        return delete_examiner_with_records(user_id, current_admin, db)

    if target_user.role == UserRole.ADMIN.value:
        return delete_admin_with_records(user_id, current_admin, db)

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="This account type cannot be deleted.",
    )

