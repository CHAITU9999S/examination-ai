
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.models import User


# ==========================================
# USER LOOKUP
# ==========================================

def get_user_by_id(
    db: Session,
    user_id: int,
):
    """Retrieve a user using their database ID."""

    user = db.query(User).filter(
        User.id == user_id,
    ).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found.",
        )

    return user


def get_user_by_email(
    db: Session,
    email: str,
):
    """Retrieve a user using their email address."""

    normalized_email = email.strip().lower()

    return db.query(User).filter(
        User.email == normalized_email,
    ).first()


# ==========================================
# USER LISTING
# ==========================================

def list_users(
    db: Session,
    role: str | None = None,
    active_only: bool = False,
    skip: int = 0,
    limit: int = 100,
):
    """Return users with optional role and active-status filters."""

    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip value cannot be negative.",
        )

    if limit < 1 or limit > 500:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 500.",
        )

    query = db.query(User)

    if role is not None:
        if role not in {"student", "examiner", "admin"}:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid user role.",
            )

        query = query.filter(
            User.role == role,
        )

    if active_only:
        query = query.filter(
            User.is_active.is_(True),
        )

    return query.order_by(
        User.id.asc(),
    ).offset(skip).limit(limit).all()


# ==========================================
# PROFILE UPDATE
# ==========================================

def update_user_profile(
    db: Session,
    user_id: int,
    full_name: str | None = None,
    department: str | None = None,
):
    """Update a user's own profile information."""

    user = get_user_by_id(
        db,
        user_id,
    )

    if full_name is not None:
        normalized_name = full_name.strip()

        if not normalized_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name cannot be empty.",
            )

        if len(normalized_name) > 150:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Full name cannot exceed 150 characters.",
            )

        user.full_name = normalized_name

    if department is not None:
        normalized_department = department.strip()

        if len(normalized_department) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Department cannot exceed 100 characters.",
            )

        user.department = normalized_department or None

    try:
        db.commit()
        db.refresh(user)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update user profile.",
        )

    return user


# ==========================================
# ACCOUNT STATUS
# ==========================================

def update_user_status(
    db: Session,
    user_id: int,
    is_active: bool,
    actor: User,
):
    """Activate or deactivate a user with admin authorization."""

    actor_role = getattr(
        actor.role,
        "value",
        actor.role,
    )

    if actor_role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can change account status.",
        )

    user = get_user_by_id(
        db,
        user_id,
    )

    target_role = getattr(
        user.role,
        "value",
        user.role,
    )

    actor_role = getattr(
        actor.role,
        "value",
        actor.role,
    )

    if (
        not is_active
        and target_role == "admin"
        and user.id == actor.id
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An administrator cannot deactivate their own account.",
        )

    if not is_active and target_role == "admin":
        active_admin_count = db.query(User).filter(
            User.role == "admin",
            User.is_active.is_(True),
        ).count()

        if active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="The last active administrator cannot be deactivated.",
            )

    user.is_active = is_active

    try:
        db.commit()
        db.refresh(user)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to update account status.",
        )

    return user


# ==========================================
# PASSWORD CHANGE
# ==========================================

def change_user_password(
    db: Session,
    user_id: int,
    current_password: str,
    new_password: str,
):
    """Change the password after verifying the existing password."""

    user = get_user_by_id(
        db,
        user_id,
    )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Inactive accounts cannot change passwords.",
        )

    if not verify_password(
        current_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )

    if verify_password(
        new_password,
        user.password_hash,
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password.",
        )

    user.password_hash = hash_password(new_password)

    try:
        db.commit()
        db.refresh(user)

    except SQLAlchemyError:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to change password.",
        )

    return user
