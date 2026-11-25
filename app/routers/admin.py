from datetime import datetime, timezone

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

    if target_user.role == UserRole.STUDENT.value:
        try:
            session_ids = [
                row[0] for row in db.query(ExamSession.id).filter(
                    ExamSession.student_id == target_user.id
                ).all()
            ]
            answer_ids = []
            if session_ids:
                answer_ids = [
                    row[0] for row in db.query(Answer.id).filter(
                        Answer.session_id.in_(session_ids)
                    ).all()
                ]

            if answer_ids:
                db.query(AnswerMarkRevision).filter(
                    AnswerMarkRevision.answer_id.in_(answer_ids)
                ).delete(synchronize_session=False)

            if session_ids:
                db.query(Result).filter(
                    Result.session_id.in_(session_ids)
                ).delete(synchronize_session=False)
                db.query(ProctorEvent).filter(
                    ProctorEvent.session_id.in_(session_ids)
                ).delete(synchronize_session=False)
                db.query(Answer).filter(
                    Answer.session_id.in_(session_ids)
                ).delete(synchronize_session=False)
                db.query(ExamSession).filter(
                    ExamSession.id.in_(session_ids)
                ).delete(synchronize_session=False)

            db.query(ExamAssignment).filter(
                or_(
                    ExamAssignment.student_id == target_user.id,
                    ExamAssignment.assigned_by == target_user.id,
                )
            ).delete(synchronize_session=False)

            # Remove old activity entries linked to this account.
            db.query(AdminActivityLog).filter(
                or_(
                    AdminActivityLog.actor_user_id == target_user.id,
                    AdminActivityLog.target_user_id == target_user.id,
                )
            ).delete(synchronize_session=False)

            record_admin_activity(
                db=db,
                actor_user_id=current_admin.id,
                target_user_id=None,
                action="student_deleted",
                details={
                    "target_user_id": target_user.id,
                    **deleted_user_details,
                    "deleted_sessions": len(session_ids),
                    "deleted_answers": len(answer_ids),
                },
            )
            db.delete(target_user)
            db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="This Student account could not be deleted because another record still depends on it.",
            )

        return MessageResponse(
            message="The Student account and its examination assignments, sessions, answers, marks, results, and proctoring records were deleted."
        )

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

        if target_user.role == UserRole.STUDENT.value:
            assigned_exam_ids = db.query(
                ExamAssignment.exam_id
            ).filter(
                ExamAssignment.student_id == target_user.id
            )

            session_exam_ids = db.query(
                ExamSession.exam_id
            ).filter(
                ExamSession.student_id == target_user.id
            )

            linked_exams = db.query(
                Exam, User
            ).outerjoin(
                User, User.id == Exam.created_by
            ).filter(
                or_(
                    Exam.id.in_(assigned_exam_ids),
                    Exam.id.in_(session_exam_ids),
                )
            ).order_by(
                Exam.title.asc()
            ).all()

            if linked_exams:
                exam_details = "; ".join(
                    (
                        f"{exam.title} — Created by: "
                        f"{creator.full_name if creator else 'Unknown'} "
                        f"({creator.role.title() if creator else 'Unknown'})"
                    )
                    for exam, creator in linked_exams
                )

                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        "This student is linked to examination records and "
                        "cannot be permanently deleted. Deactivate the "
                        "student account instead. Linked examinations: "
                        f"{exam_details}"
                    )
                )

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This account is linked to existing examination or audit "
                "records and cannot be permanently deleted. Deactivate it "
                "instead."
            )
        )

    return MessageResponse(message="User account deleted successfully.")


@router.delete(
    "/examiners/{user_id}/with-records",
    response_model=MessageResponse
)
def delete_examiner_with_records(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete an Examiner and the records that belong to their work."""

    examiner = db.query(User).filter(
        User.id == user_id,
        User.role == UserRole.EXAMINER.value,
    ).first()

    if examiner is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Examiner account not found.",
        )

    exam_ids = [
        row[0] for row in db.query(Exam.id).filter(
            Exam.created_by == examiner.id
        ).all()
    ]

    # Audit revisions authored by the deleted account are removed below;
    # revisions authored by other staff and all examination data are retained.

    try:
        session_conditions = [
            ExamSession.student_id == examiner.id,
        ]
        if exam_ids:
            session_conditions.append(ExamSession.exam_id.in_(exam_ids))
        session_ids = [
            row[0] for row in db.query(ExamSession.id).filter(
                or_(*session_conditions)
            ).all()
        ]

        answer_ids = [
            row[0] for row in db.query(Answer.id).filter(
                Answer.session_id.in_(session_ids)
            ).all()
        ] if session_ids else []

        owned_question_ids = [
            row[0] for row in db.query(QuestionBank.id).filter(
                QuestionBank.created_by == examiner.id
            ).all()
        ]

        collection_ids = [
            row[0] for row in db.query(QuestionCollection.id).filter(
                QuestionCollection.created_by == examiner.id
            ).all()
        ]

        # Remove records that depend on the Examiner's examinations.
        if answer_ids:
            db.query(AnswerMarkRevision).filter(
                AnswerMarkRevision.answer_id.in_(answer_ids)
            ).delete(synchronize_session=False)

        if session_ids:
            db.query(Result).filter(
                Result.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(ProctorEvent).filter(
                ProctorEvent.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(Answer).filter(
                Answer.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(ExamSession).filter(
                ExamSession.id.in_(session_ids)
            ).delete(synchronize_session=False)

        if exam_ids:
            db.query(ExamAssignment).filter(
                ExamAssignment.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)
            db.query(ExamConfigurationRevision).filter(
                ExamConfigurationRevision.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)
            db.query(ExamQuestionMarksRevision).filter(
                ExamQuestionMarksRevision.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)
            db.query(ExamQuestion).filter(
                ExamQuestion.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)

        # Remove only revision rows authored by this account, including work
        # recorded against examinations owned by other staff. The examinations,
        # final marks, and other reviewers' history remain intact.
        db.query(ExamConfigurationRevision).filter(
            ExamConfigurationRevision.changed_by == examiner.id,
        ).delete(synchronize_session=False)
        db.query(ExamQuestionMarksRevision).filter(
            ExamQuestionMarksRevision.changed_by == examiner.id,
        ).delete(synchronize_session=False)
        db.query(AnswerMarkRevision).filter(
            AnswerMarkRevision.revised_by == examiner.id,
        ).delete(synchronize_session=False)

        # Remove assignments created by this Examiner, including assignments
        # they made for examinations owned by someone else.
        db.query(ExamAssignment).filter(
            or_(
                ExamAssignment.assigned_by == examiner.id,
                ExamAssignment.student_id == examiner.id,
            )
        ).delete(synchronize_session=False)

        # Remove this Examiner's named question banks, but keep questions
        # that are still used by another exam, bank, or answer.
        if collection_ids:
            db.query(QuestionCollectionItem).filter(
                QuestionCollectionItem.collection_id.in_(collection_ids)
            ).delete(synchronize_session=False)
            db.query(QuestionCollection).filter(
                QuestionCollection.id.in_(collection_ids)
            ).delete(synchronize_session=False)

        removable_question_ids = []
        for question_id in owned_question_ids:
            used_in_exam = db.query(ExamQuestion.id).filter(
                ExamQuestion.question_id == question_id
            ).first()
            used_in_answer = db.query(Answer.id).filter(
                Answer.question_id == question_id
            ).first()
            used_in_collection = db.query(QuestionCollectionItem.id).filter(
                QuestionCollectionItem.question_id == question_id
            ).first()
            used_as_source = db.query(QuestionBank.id).filter(
                QuestionBank.source_question_id == question_id
            ).first()

            if not any((
                used_in_exam,
                used_in_answer,
                used_in_collection,
                used_as_source,
            )):
                removable_question_ids.append(question_id)

        if removable_question_ids:
            db.query(Option).filter(
                Option.question_id.in_(removable_question_ids)
            ).delete(synchronize_session=False)
            db.query(QuestionBank).filter(
                QuestionBank.id.in_(removable_question_ids)
            ).delete(synchronize_session=False)

        kept_question_ids = set(owned_question_ids) - set(removable_question_ids)
        if kept_question_ids:
            db.query(QuestionBank).filter(
                QuestionBank.id.in_(kept_question_ids)
            ).update(
                {QuestionBank.created_by: None},
                synchronize_session=False,
            )

        # Remove audit rows that name this Examiner. Keep the final deletion
        # entry under the Admin who carried out the action.
        db.query(AdminActivityLog).filter(
            or_(
                AdminActivityLog.actor_user_id == examiner.id,
                AdminActivityLog.target_user_id == examiner.id,
            )
        ).delete(synchronize_session=False)

        if exam_ids:
            db.query(Exam).filter(
                Exam.id.in_(exam_ids)
            ).delete(synchronize_session=False)

        deleted_details = {
            "target_user_id": examiner.id,
            "full_name": examiner.full_name,
            "email": examiner.email,
            "role": examiner.role,
            "deleted_examinations": len(exam_ids),
            "deleted_sessions": len(session_ids),
            "deleted_answers": len(answer_ids),
            "deleted_questions": len(removable_question_ids),
        }

        record_admin_activity(
            db=db,
            actor_user_id=current_admin.id,
            target_user_id=None,
            action="examiner_and_records_deleted",
            details=deleted_details,
        )
        db.delete(examiner)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The Examiner could not be deleted because another record "
                "still depends on this account. No records were deleted."
            ),
        )
    except Exception:
        db.rollback()
        raise

    return MessageResponse(
        message=(
            "The Examiner account and its examination records were deleted. "
            "Questions still used elsewhere were kept."
        )
    )


@router.delete(
    "/admins/{user_id}/with-records",
    response_model=MessageResponse
)
def delete_admin_with_records(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db),
):
    """Delete another Admin and the records that belong to their work."""

    admin_to_delete = db.query(User).filter(
        User.id == user_id,
        User.role == UserRole.ADMIN.value,
    ).first()

    if admin_to_delete is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Admin account not found.",
        )

    if admin_to_delete.id == current_admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account.",
        )

    active_admin_count = db.query(User).filter(
        User.role == UserRole.ADMIN.value,
        User.is_active.is_(True),
    ).count()

    if admin_to_delete.is_active and active_admin_count <= 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The last active Admin account cannot be deleted.",
        )

    exam_ids = [
        row[0] for row in db.query(Exam.id).filter(
            Exam.created_by == admin_to_delete.id
        ).all()
    ]

    # Audit revisions authored by the deleted account are removed below;
    # revisions authored by other staff and all examination data are retained.

    try:
        session_conditions = [
            ExamSession.student_id == admin_to_delete.id
        ]
        if exam_ids:
            session_conditions.append(ExamSession.exam_id.in_(exam_ids))

        session_ids = [
            row[0] for row in db.query(ExamSession.id).filter(
                or_(*session_conditions)
            ).all()
        ]

        answer_ids = [
            row[0] for row in db.query(Answer.id).filter(
                Answer.session_id.in_(session_ids)
            ).all()
        ] if session_ids else []

        owned_question_ids = [
            row[0] for row in db.query(QuestionBank.id).filter(
                QuestionBank.created_by == admin_to_delete.id
            ).all()
        ]
        collection_ids = [
            row[0] for row in db.query(QuestionCollection.id).filter(
                QuestionCollection.created_by == admin_to_delete.id
            ).all()
        ]

        # Remove records that depend on this Admin's examinations.
        if answer_ids:
            db.query(AnswerMarkRevision).filter(
                AnswerMarkRevision.answer_id.in_(answer_ids)
            ).delete(synchronize_session=False)

        if session_ids:
            db.query(Result).filter(
                Result.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(ProctorEvent).filter(
                ProctorEvent.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(Answer).filter(
                Answer.session_id.in_(session_ids)
            ).delete(synchronize_session=False)
            db.query(ExamSession).filter(
                ExamSession.id.in_(session_ids)
            ).delete(synchronize_session=False)

        if exam_ids:
            db.query(ExamAssignment).filter(
                ExamAssignment.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)
            db.query(ExamConfigurationRevision).filter(
                ExamConfigurationRevision.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)
            db.query(ExamQuestionMarksRevision).filter(
                ExamQuestionMarksRevision.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)
            db.query(ExamQuestion).filter(
                ExamQuestion.exam_id.in_(exam_ids)
            ).delete(synchronize_session=False)

        # Remove revision history authored by this Admin, while preserving
        # examinations, final marks, and revisions authored by other staff.
        db.query(ExamConfigurationRevision).filter(
            ExamConfigurationRevision.changed_by == admin_to_delete.id,
        ).delete(synchronize_session=False)
        db.query(ExamQuestionMarksRevision).filter(
            ExamQuestionMarksRevision.changed_by == admin_to_delete.id,
        ).delete(synchronize_session=False)
        db.query(AnswerMarkRevision).filter(
            AnswerMarkRevision.revised_by == admin_to_delete.id,
        ).delete(synchronize_session=False)

        # Remove assignments made by this Admin and assignments where
        # this Admin was added as a student.
        db.query(ExamAssignment).filter(
            or_(
                ExamAssignment.assigned_by == admin_to_delete.id,
                ExamAssignment.student_id == admin_to_delete.id,
            )
        ).delete(synchronize_session=False)

        # Remove this Admin's named question banks, but keep questions
        # that are still used by another exam, bank, or answer.
        if collection_ids:
            db.query(QuestionCollectionItem).filter(
                QuestionCollectionItem.collection_id.in_(collection_ids)
            ).delete(synchronize_session=False)
            db.query(QuestionCollection).filter(
                QuestionCollection.id.in_(collection_ids)
            ).delete(synchronize_session=False)

        removable_question_ids = []
        for question_id in owned_question_ids:
            used_in_exam = db.query(ExamQuestion.id).filter(
                ExamQuestion.question_id == question_id
            ).first()
            used_in_answer = db.query(Answer.id).filter(
                Answer.question_id == question_id
            ).first()
            used_in_collection = db.query(QuestionCollectionItem.id).filter(
                QuestionCollectionItem.question_id == question_id
            ).first()
            used_as_source = db.query(QuestionBank.id).filter(
                QuestionBank.source_question_id == question_id
            ).first()

            if not any((
                used_in_exam,
                used_in_answer,
                used_in_collection,
                used_as_source,
            )):
                removable_question_ids.append(question_id)

        if removable_question_ids:
            db.query(Option).filter(
                Option.question_id.in_(removable_question_ids)
            ).delete(synchronize_session=False)
            db.query(QuestionBank).filter(
                QuestionBank.id.in_(removable_question_ids)
            ).delete(synchronize_session=False)

        kept_question_ids = set(owned_question_ids) - set(removable_question_ids)
        if kept_question_ids:
            db.query(QuestionBank).filter(
                QuestionBank.id.in_(kept_question_ids)
            ).update(
                {QuestionBank.created_by: None},
                synchronize_session=False,
            )

        # Remove audit rows linked to the deleted Admin. Keep the final
        # deletion entry under the Admin who carried out this action.
        db.query(AdminActivityLog).filter(
            or_(
                AdminActivityLog.actor_user_id == admin_to_delete.id,
                AdminActivityLog.target_user_id == admin_to_delete.id,
            )
        ).delete(synchronize_session=False)

        if exam_ids:
            db.query(Exam).filter(
                Exam.id.in_(exam_ids)
            ).delete(synchronize_session=False)

        deleted_details = {
            "target_user_id": admin_to_delete.id,
            "full_name": admin_to_delete.full_name,
            "email": admin_to_delete.email,
            "role": admin_to_delete.role,
            "deleted_examinations": len(exam_ids),
            "deleted_sessions": len(session_ids),
            "deleted_answers": len(answer_ids),
            "deleted_questions": len(removable_question_ids),
        }

        record_admin_activity(
            db=db,
            actor_user_id=current_admin.id,
            target_user_id=None,
            action="admin_and_records_deleted",
            details=deleted_details,
        )
        db.delete(admin_to_delete)
        db.commit()

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "The Admin could not be deleted because another record still "
                "depends on this account. No records were deleted."
            ),
        )
    except Exception:
        db.rollback()
        raise

    return MessageResponse(
        message=(
            "The Admin account and its examination records were deleted. "
            "Questions still used elsewhere were kept."
        )
    )


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
    return {
        "available": not used,
        "used": used,
        "message": (
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

