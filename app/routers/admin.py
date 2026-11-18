from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import get_db
from app.dependencies import get_current_admin
from app.models import User
from app.schemas import (
    AdminUserCreate,
    MessageResponse,
    UserResponse,
    UserRole,
)


router = APIRouter(
    prefix="/admin",
    tags=["Admin Management"]
)


# -----------------------------------------
# CREATE ADMIN OR EXAMINER ACCOUNT
# -----------------------------------------

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
    """
    Only an authenticated Admin can create
    Admin and Examiner accounts.
    """

    if user_data.role not in (
        UserRole.ADMIN,
        UserRole.EXAMINER
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Admins can create only Admin or Examiner accounts."
        )

    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        is_active=True
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# -----------------------------------------
# LIST ALL USERS
# -----------------------------------------

@router.get(
    "/users",
    response_model=list[UserResponse]
)
def list_users(
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Only Admins can view the user account list.
    """

    return db.query(User).order_by(User.id).all()


# -----------------------------------------
# DELETE ADMIN, EXAMINER OR STUDENT
# -----------------------------------------

@router.delete(
    "/users/{user_id}",
    response_model=MessageResponse
)
def delete_user(
    user_id: int,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Only an Admin can delete user accounts.

    An Admin cannot delete their own account.
    The last active Admin account cannot be deleted.
    """

    target_user = db.query(User).filter(
        User.id == user_id
    ).first()

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

    if target_user.role == UserRole.ADMIN:
        active_admin_count = db.query(User).filter(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True)
        ).count()

        if target_user.is_active and active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active Admin account cannot be deleted."
            )

    db.delete(target_user)

    try:
        db.commit()
    except Exception:
        db.rollback()

        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This account is linked to existing examination records "
                "and cannot currently be deleted."
            )
        )

    return MessageResponse(
        message="User account deleted successfully."
    )


# -----------------------------------------
# ACTIVATE OR DEACTIVATE USER ACCOUNT
# -----------------------------------------

@router.patch(
    "/users/{user_id}/status",
    response_model=UserResponse
)
def update_user_status(
    user_id: int,
    is_active: bool,
    current_admin: User = Depends(get_current_admin),
    db: Session = Depends(get_db)
):
    """
    Only Admins can activate or deactivate accounts.
    """

    target_user = db.query(User).filter(
        User.id == user_id
    ).first()

    if target_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User account not found."
        )

    if target_user.id == current_admin.id and not is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account."
        )

    if target_user.role == UserRole.ADMIN and not is_active:
        active_admin_count = db.query(User).filter(
            User.role == UserRole.ADMIN,
            User.is_active.is_(True)
        ).count()

        if target_user.is_active and active_admin_count <= 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The last active Admin cannot be deactivated."
            )

    target_user.is_active = is_active

    db.commit()
    db.refresh(target_user)

    return target_user
