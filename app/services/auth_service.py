
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.auth import (
    create_access_token,
    get_password_hash,
    verify_password,
)
from app.models import User


# ==========================================
# USER AUTHENTICATION
# ==========================================

def authenticate_user(
    db: Session,
    email: str,
    password: str,
):
    """Authenticate a user using email and password."""

    normalized_email = email.strip().lower()

    user = db.query(User).filter(
        User.email == normalized_email,
    ).first()

    if user is None:
        return None

    if not user.is_active:
        return None

    if not verify_password(
        password,
        user.password_hash,
    ):
        return None

    return user


# ==========================================
# USER REGISTRATION
# ==========================================

def register_student(
    db: Session,
    full_name: str,
    email: str,
    password: str,
    department: str | None = None,
):
    """Register a new student account."""

    normalized_email = email.strip().lower()

    existing_user = db.query(User).filter(
        User.email == normalized_email,
    ).first()

    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    user = User(
        full_name=full_name.strip(),
        email=normalized_email,
        department=department.strip() if department else None,
        password_hash=get_password_hash(password),
        role="student",
        is_active=True,
        created_at=datetime.now(timezone.utc).replace(
            tzinfo=None,
        ),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()
        raise

    return user


# ==========================================
# ACCESS TOKEN
# ==========================================

def create_user_access_token(
    user: User,
):
    """Create an access token for an authenticated user."""

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is invalid or inactive.",
        )

    return create_access_token(
        data={
            "sub": str(user.id),
            "role": user.role,
            "token_type": "access",
        },
    )


# ==========================================
# PASSWORD CHANGE
# ==========================================

def change_user_password(
    db: Session,
    user: User,
    current_password: str,
    new_password: str,
):
    """Change a user's password after verifying the old password."""

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is invalid or inactive.",
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

    user.password_hash = get_password_hash(new_password)

    try:
        db.commit()
        db.refresh(user)

    except Exception:
        db.rollback()
        raise

    return user
