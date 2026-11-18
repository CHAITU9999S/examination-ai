from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import hash_password, verify_password
from app.database import get_db
from app.dependencies import get_current_user
from app.models import User
from app.schemas import (
    MessageResponse,
    PasswordChange,
    UserResponse,
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
    """
    Return the profile of the authenticated user.
    """

    return current_user


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
    """
    Allow an authenticated user to change their password.
    """

    if not verify_password(
        password_data.current_password,
        current_user.hashed_password
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect."
        )

    if password_data.current_password == password_data.new_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="New password must be different from the current password."
        )

    current_user.hashed_password = hash_password(
        password_data.new_password
    )

    db.commit()

    return MessageResponse(
        message="Password changed successfully."
)
