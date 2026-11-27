from datetime import datetime, timezone
import secrets

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from app.auth import hash_password
from app.database import get_db
from app.dependencies import get_current_admin, require_role
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
from app.services.session_service import generate_session_question_ids


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
            AdminActivityLog.action.in_(
                (
                    "examination_created",
                    "exam_configuration_updated",
                    "examination_scheduled",
                    "examination_published",
                    "examination_deleted",
                    "exam_question_added",
                    "exam_question_removed_from_bank",
                    "exam_questions_reused",
                    "exam_questions_copied_from_banks",
                    "exam_question_bank_deleted",
                    "exam_question_marks_updated",
                    "exam_question_timer_configured",
                    "exam_question_negative_marks_configured",
                    "exam_assigned_to_students",
                    "exam_student_access_revoked",
                    "question_bank_created",
                    "question_bank_updated",
                    "question_bank_deleted",
                    "question_added_to_bank",
                    "question_updated_in_bank",
                    "question_deleted_from_bank",
                    "question_removed_from_bank",
                )
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


def _build_student_performance(current_user: User, db: Session, include_all_assignments: bool = False):
    """Build student assignment and performance summaries. The caller controls scope.
    """
    StudentAccount = aliased(User)
    CreatorAccount = aliased(User)
    AssignerAccount = aliased(User)

    students = db.query(User).filter(
        User.role == UserRole.STUDENT.value,
        User.is_deleted.is_(False),
    ).order_by(User.full_name.asc()).all()

    student_items = {
        student.id: {
            "student_id": student.id,
            "student_name": student.full_name,
            "student_email": student.email,
            "department": student.department,
            "total_assigned_examinations": 0,
            "total_taken_examinations": 0,
            "total_started_examinations": 0,
            "attempts": [],
        }
        for student in students
    }

    assignment_query = db.query(
        ExamAssignment, Exam, StudentAccount, CreatorAccount, AssignerAccount
    ).join(
        Exam, Exam.id == ExamAssignment.exam_id
    ).join(
        StudentAccount, StudentAccount.id == ExamAssignment.student_id
    ).outerjoin(
        CreatorAccount, CreatorAccount.id == Exam.created_by
    ).outerjoin(
        AssignerAccount, AssignerAccount.id == ExamAssignment.assigned_by
    ).filter(
        ExamAssignment.is_active.is_(True),
        StudentAccount.role == UserRole.STUDENT.value,
        StudentAccount.is_deleted.is_(False),
    )

    if not include_all_assignments:
        assignment_query = assignment_query.filter(
            ExamAssignment.assigned_by == current_user.id
        )

    assignment_rows = assignment_query.order_by(
        StudentAccount.full_name.asc(),
        ExamAssignment.assigned_at.desc(),
        Exam.id.desc(),
    ).limit(20000).all()

    if not include_all_assignments:
        assigned_student_ids = {student.id for _, _, student, _, _ in assignment_rows}
        student_items = {
            student_id: item
            for student_id, item in student_items.items()
            if student_id in assigned_student_ids
        }

    flat_performance = []
    now = datetime.utcnow()
    for assignment, exam, student, creator, assigner in assignment_rows:
        session = db.query(ExamSession).filter(
            ExamSession.exam_id == exam.id,
            ExamSession.student_id == student.id,
        ).order_by(ExamSession.id.desc()).first()

        selection_rules = exam.selection_rules if isinstance(exam.selection_rules, dict) else {}
        uses_type_difficulty_configuration = any(
            key in selection_rules
            for key in ("group_counts", "difficulty", "difficulty_counts", "question_type_counts")
        )
        if (
            not uses_type_difficulty_configuration
            and exam.total_marks is not None
            and (
                session is None
                or (
                    session.status == "not_started"
                    and not session.selected_question_ids
                    and session.prestart_stage is None
                )
            )
        ):
            try:
                selected_ids = generate_session_question_ids(
                    exam=exam,
                    student_id=student.id,
                    db=db,
                )
                if session is None:
                    session = ExamSession(
                        exam_id=exam.id,
                        student_id=student.id,
                        started_at=None,
                        expires_at=None,
                        status="not_started",
                        prestart_stage=None,
                        prestart_expires_at=None,
                        selected_question_ids=selected_ids,
                        visited_question_ids=[],
                    )
                    db.add(session)
                else:
                    session.selected_question_ids = selected_ids
                db.commit()
                db.refresh(session)
            except ValueError:
                db.rollback()

        result = (
            db.query(Result).filter(Result.session_id == session.id).first()
            if session is not None else None
        )

        question_ids = list(session.selected_question_ids or []) if session else []
        if not question_ids and not (
            not uses_type_difficulty_configuration and exam.total_marks is not None
        ):
            question_ids = [
                row[0] for row in db.query(ExamQuestion.question_id).filter(
                    ExamQuestion.exam_id == exam.id
                ).order_by(ExamQuestion.question_order.asc(), ExamQuestion.id.asc()).all()
            ]

        question_rows = db.query(
            QuestionBank.id, QuestionBank.marks
        ).filter(
            QuestionBank.id.in_(question_ids or [-1])
        ).all()
        question_marks = {
            question_id: float(maximum_marks or 0)
            for question_id, maximum_marks in question_rows
        }
        total_questions = (
            len(question_ids)
            if question_ids
            else int(exam.total_questions or 0)
        )
        total_marks = (
            float(result.total_marks)
            if result is not None and result.total_marks is not None
            else sum(question_marks.values())
            if question_marks
            else float(exam.total_marks)
            if not uses_type_difficulty_configuration and exam.total_marks is not None
            else None
        )

        answers = (
            db.query(Answer).filter(Answer.session_id == session.id).all()
            if session is not None else []
        )
        evaluated_answers = [
            answer for answer in answers if answer.awarded_marks is not None
        ]
        positive_marks = round(sum(
            max(0.0, float(answer.awarded_marks))
            for answer in evaluated_answers
        ), 2)
        negative_marks = round(sum(
            abs(min(0.0, float(answer.awarded_marks)))
            for answer in evaluated_answers
        ), 2)
        correct_answers = 0
        wrong_answers = 0
        partially_correct_answers = 0
        for answer in evaluated_answers:
            maximum = question_marks.get(answer.question_id)
            if maximum is None:
                continue
            awarded = float(answer.awarded_marks)
            if abs(awarded - maximum) < 0.0001:
                correct_answers += 1
            elif awarded <= 0:
                wrong_answers += 1
            elif awarded < maximum:
                partially_correct_answers += 1

        marked_values = [float(answer.awarded_marks) for answer in evaluated_answers]
        obtained_marks = (
            float(result.obtained_marks)
            if result is not None and result.obtained_marks is not None
            else round(sum(marked_values), 2) if marked_values else None
        )
        percentage = (
            float(result.percentage)
            if result is not None and result.percentage is not None
            else (
                round(obtained_marks / total_marks * 100, 2)
                if obtained_marks is not None and total_marks
                else None
            )
        )
        status_value = session.status if session is not None else "not_started"
        if (
            exam.end_time is not None
            and now >= exam.end_time
            and status_value in {"not_started", "in_progress"}
        ):
            status_value = "expired"
        status_labels = {
            "not_started": "Not Started",
            "in_progress": "In Progress",
            "submitted": "Submitted",
            "auto_submitted": "Auto Submitted",
            "expired": "Expired",
            "completed": "Completed",
        }
        published = bool(result and result.is_published)
        is_started = bool(session is not None and session.started_at is not None)
        is_taken = bool(
            session is not None and (
                session.submitted_at is not None
                or status_value in ("submitted", "auto_submitted", "completed")
                or (status_value == "expired" and session.started_at is not None)
            )
        )
        attempt = {
            "assignment_id": assignment.id,
            "assigned_at": _utc_iso(assignment.assigned_at),
            "session_id": session.id if session else None,
            "exam_id": exam.id,
            "exam_title": exam.title,
            "exam_subject": exam.subject,
            "exam_start_time": _utc_iso(exam.start_time),
            "exam_end_time": _utc_iso(exam.end_time),
            "creator_id": exam.created_by,
            "creator_name": creator.full_name if creator else "Deleted account",
            "assigned_by_name": assigner.full_name if assigner else "Deleted account",
            "assigned_by_role": assigner.role if assigner else None,
            "started_at": _utc_iso(session.started_at) if session else None,
            "submitted_at": _utc_iso(session.submitted_at) if session else None,
            "session_status": status_value,
            "status_label": status_labels.get(status_value, str(status_value or "Not Started").replace("_", " ").title()),
            "is_started": is_started,
            "is_taken": is_taken,
            "total_questions": total_questions,
            "correct_answers": correct_answers,
            "wrong_answers": wrong_answers,
            "partially_correct_answers": partially_correct_answers,
            "unanswered_questions": max(0, total_questions - len(answers)),
            "positive_marks": positive_marks,
            "negative_marks": negative_marks,
            "obtained_marks": obtained_marks,
            "total_marks": total_marks,
            "percentage": percentage,
            "grade": (
                (result.grade or _performance_grade(result.percentage))
                if published and result is not None
                else None
            ),
            "result_published": published,
            "marks_status": (
                "Result published" if published
                else "Evaluated — awaiting publication" if result is not None
                else "Evaluation in progress" if marked_values
                else "Not evaluated" if is_taken
                else "Not started" if not is_started
                else "In progress"
            ),
            "published_at": _utc_iso(result.published_at) if result else None,
        }

        if student.id in student_items:
            student_item = student_items[student.id]
            student_item["attempts"].append(attempt)
            student_item["total_assigned_examinations"] += 1
            student_item["total_started_examinations"] += int(is_started)
            student_item["total_taken_examinations"] += int(is_taken)

        flat_performance.append({
            "result_id": result.id if result else None,
            "student_id": student.id,
            "student_name": student.full_name,
            **attempt,
        })

    return {
        "total_students": len(student_items),
        "total_assignments": len(flat_performance),
        "total_taken_examinations": sum(
            student["total_taken_examinations"] for student in student_items.values()
        ),
        "total_published_results": sum(
            1 for attempt in flat_performance if attempt["result_published"]
        ),
        "students": list(student_items.values()),
        # Keep the earlier flat response key for existing API consumers.
        "performance": flat_performance,
    }


@router.get("/performance")
def get_historical_student_performance(
    current_user: User = Depends(require_role("admin", "examiner")),
    db: Session = Depends(get_db),
):
    """Student Tracking: only assignments created by the logged-in account."""
    return _build_student_performance(current_user, db, include_all_assignments=False)


@router.get("/student-performance")
def get_platform_student_performance(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Admin-only Student Performance across all Admin and Examiner assignments."""
    return _build_student_performance(current_admin, db, include_all_assignments=True)


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
        ExamAssignment.is_active.is_(True),
        Exam.start_time.is_not(None),
        Exam.start_time > datetime.now(timezone.utc).replace(tzinfo=None),
        StudentAccount.is_deleted.is_(False),
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

