from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import User, AdminActivity
from app.admin_schemas import AdminAccountCreate, UserStatusUpdate
from app.auth import hash_password
from app.services.admin_service import (
    record_admin_activity,
    get_dashboard_statistics
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin Management"]
)


def create_managed_account(
    db: Session,
    account: AdminAccountCreate,
    role: str,
    admin: User
):
    """
    Create an Examiner or another Admin account.
    Only authenticated Admins can reach the endpoints using this helper.
    """

    existing_user = (
        db.query(User)
        .filter(User.email == account.email)
        .first()
    )

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists"
        )

    new_user = User(
        full_name=account.full_name,
        email=account.email,
        department=account.department,
        password_hash=hash_password(account.password),
        role=role,
        is_active=True
    )

    db.add(new_user)
    db.flush()

    record_admin_activity(
        db=db,
        actor_user_id=admin.id,
        target_user_id=new_user.id,
        action=f"created_{role}_account",
        details={
            "created_email": new_user.email,
            "created_role": role
        }
    )

    db.commit()
    db.refresh(new_user)

    return {
        "message": f"{role.capitalize()} account created successfully",
        "user": {
            "id": new_user.id,
            "full_name": new_user.full_name,
            "email": new_user.email,
            "department": new_user.department,
            "role": new_user.role,
            "is_active": new_user.is_active,
            "created_at": new_user.created_at
        }
    }


@router.get("/dashboard")
def admin_dashboard(
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    """
    View dashboard statistics.
    """

    return {
        "message": "Admin dashboard statistics",
        "admin": {
            "id": admin.id,
            "full_name": admin.full_name,
            "email": admin.email
        },
        "statistics": get_dashboard_statistics(db)
    }


@router.get("/users")
def list_users(
    role: str = None,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    """
    List user accounts, optionally filtered by role.
    """

    query = db.query(User)

    if role is not None:
        allowed_roles = ["student", "examiner", "admin"]

        if role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid role filter"
            )

        query = query.filter(User.role == role)

    total = query.count()

    users = (
        query
        .order_by(User.id.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "users": [
            {
                "id": user.id,
                "full_name": user.full_name,
                "email": user.email,
                "department": user.department,
                "role": user.role,
                "is_active": user.is_active,
                "created_at": user.created_at
            }
            for user in users
        ]
    }


@router.post(
    "/examiners",
    status_code=status.HTTP_201_CREATED
)
def create_examiner(
    account: AdminAccountCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    """
    Create an Examiner account.
    """

    return create_managed_account(
        db=db,
        account=account,
        role="examiner",
        admin=admin
    )


@router.post(
    "/admins",
    status_code=status.HTTP_201_CREATED
)
def create_additional_admin(
    account: AdminAccountCreate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    """
    Create an additional Admin account.
    Existing Admin authentication is required.
    """

    return create_managed_account(
        db=db,
        account=account,
        role="admin",
        admin=admin
    )


@router.patch("/users/{user_id}/status")
def update_user_status(
    user_id: int,
    update: UserStatusUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    """
    Activate or deactivate a user account.
    """

    target_user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found"
        )

    if target_user.id == admin.id and not update.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own Admin account"
        )

    if (
        target_user.role == "admin"
        and target_user.is_active
        and not update.is_active
    ):
        active_admin_count = (
            db.query(User)
            .filter(
                User.role == "admin",
                User.is_active.is_(True)
            )
            .count()
        )

        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active Admin account cannot be deactivated"
            )

    old_status = target_user.is_active
    target_user.is_active = update.is_active

    record_admin_activity(
        db=db,
        actor_user_id=admin.id,
        target_user_id=target_user.id,
        action=(
            "activated_user"
            if update.is_active
            else "deactivated_user"
        ),
        details={
            "previous_status": old_status,
            "new_status": update.is_active,
            "target_role": target_user.role
        }
    )

    db.commit()
    db.refresh(target_user)

    return {
        "message": (
            "User account activated successfully"
            if target_user.is_active
            else "User account deactivated successfully"
        ),
        "user": {
            "id": target_user.id,
            "full_name": target_user.full_name,
            "email": target_user.email,
            "role": target_user.role,
            "is_active": target_user.is_active
        }
    }


@router.get("/activity-logs")
def get_admin_activity_logs(
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    admin: User = Depends(require_role("admin"))
):
    """
    View recorded Admin activities.
    """

    query = db.query(AdminActivity)

    total = query.count()

    logs = (
        query
        .order_by(AdminActivity.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "activities": [
            {
                "id": log.id,
                "actor_user_id": log.actor_user_id,
                "target_user_id": log.target_user_id,
                "action": log.action,
                "details": log.details,
                "created_at": log.created_at
            }
            for log in logs
        ]
  }
      
