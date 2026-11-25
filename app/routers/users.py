
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models import LoginHistory, User
from app.schemas import (
    MessageResponse,
    PasswordChange,
    UserProfileUpdate,
    UserResponse,
    LoginHistoryResponse,
)


router = APIRouter(
    prefix="/users",
    tags=["Users"]
)


# -----------------------------------------
# GET CURRENT USER PROFILE
# -----------------------------------------

@router.get(
    "/me",
    response_model=UserResponse
)
def get_my_profile(
    current_user: User = Depends(get_current_user)
):
    """Return the authenticated user's profile."""

    return current_user


# -----------------------------------------
# UPDATE CURRENT USER PROFILE
# -----------------------------------------

@router.patch(
    "/me/profile",
    response_model=UserResponse
)
def update_my_profile(
    profile_data: UserProfileUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Update only the authenticated user's profile, with a separate limit per field."""

    # Lock the account row so simultaneous requests cannot exceed a field's limit.
    user = db.query(User).filter(
        User.id == current_user.id
    ).with_for_update().populate_existing().one()

    submitted = profile_data.model_dump(exclude_unset=True)
    if not submitted:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least one profile detail to update.",
        )

    field_limits = {
        "full_name": "full_name_edit_count",
        "email": "email_edit_count",
        "department": "department_edit_count",
        "date_of_birth": "date_of_birth_edit_count",
    }
    changes = {}

    for field, value in submitted.items():
        if field in ("full_name", "email") and value is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field.replace('_', ' ').title()} cannot be empty.",
            )

        if field == "full_name":
            value = value.strip()
            if len(value) < 2:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="Name must contain at least 2 characters.",
                )
        elif field == "email":
            value = str(value).strip().lower()
        elif field == "department" and value is not None:
            value = value.strip() or None

        current_value = getattr(user, field)
        if field == "email":
            current_value = current_value.strip().lower()

        if value == current_value:
            continue

        counter_field = field_limits[field]
        if getattr(user, counter_field) >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"You have used all 3 edit chances for {field.replace('_', ' ')}.",
            )

        changes[field] = value

    if not changes:
        return user

    if "email" in changes:
        existing = db.query(User).filter(
            func.lower(User.email) == changes["email"],
            User.id != user.id,
        ).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account with this email already exists.",
            )

    for field, value in changes.items():
        setattr(user, field, value)
        counter_field = field_limits[field]
        setattr(user, counter_field, getattr(user, counter_field) + 1)

    try:
        db.commit()
        db.refresh(user)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists.",
        )

    return user


# -----------------------------------------
# CURRENT USER LOGIN HISTORY
# -----------------------------------------

@router.get(
    "/me/login-history",
    response_model=list[LoginHistoryResponse],
)
def get_my_login_history(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return only the latest ten successful logins for the authenticated user."""

    return db.query(LoginHistory).filter(
        LoginHistory.user_id == current_user.id
    ).order_by(
        LoginHistory.logged_in_at.desc(),
        LoginHistory.id.desc(),
    ).limit(10).all()


# -----------------------------------------
# CHANGE CURRENT USER PASSWORD
# -----------------------------------------

@router.patch(
    "/me/password",
    response_model=MessageResponse
)
def change_my_password(
    password_data: PasswordChange,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Allow an authenticated user to change their password."""

    if not verify_password(
        password_data.current_password,
        current_user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )

    if (
        password_data.current_password
        == password_data.new_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "New password must be different "
                "from the current password."
            )
        )

    current_user.password_hash = hash_password(
        password_data.new_password
    )

    db.commit()
    db.refresh(current_user)

    return MessageResponse(
        message="Password changed successfully."
)
    
