import hmac
import os

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import User
from app.schemas import (
    InitialAdminBootstrapRequest,
    LoginRequest,
    StudentRegister,
    TokenResponse,
    UserResponse,
    UserRole,
)
from scripts.create_initial_admin import create_initial_admin


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# -----------------------------------------
# ONE-TIME INITIAL ADMIN BOOTSTRAP
# -----------------------------------------

@router.post(
    "/bootstrap-admin",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def bootstrap_initial_admin(
    admin_data: InitialAdminBootstrapRequest,
    setup_token: str | None = Header(
        default=None,
        alias="X-Admin-Bootstrap-Token"
    ),
    db: Session = Depends(get_db)
):
    """
    Create the first Admin using a temporary server-side setup token.

    The endpoint is disabled unless INITIAL_ADMIN_SETUP_TOKEN is set.
    It can create an Admin only while no Admin account exists.
    """

    configured_token = os.getenv("INITIAL_ADMIN_SETUP_TOKEN")

    # Return 404 when disabled so the bootstrap route is not advertised
    # as an available setup mechanism after the temporary token is removed.
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found."
        )

    if len(configured_token) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Initial Admin setup is not securely configured."
        )

    if not setup_token or not hmac.compare_digest(
        setup_token,
        configured_token
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Admin setup token."
        )

    try:
        admin = create_initial_admin(
            db=db,
            full_name=admin_data.full_name,
            email=str(admin_data.email),
            password=admin_data.password,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc)
        ) from exc
    except RuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc)
        ) from exc

    return admin


# -----------------------------------------
# STUDENT PUBLIC REGISTRATION
# -----------------------------------------

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register_student(
    student_data: StudentRegister,
    db: Session = Depends(get_db)
):
    """
    Allow public registration for Students only.
    Admin and Examiner accounts must be created by an Admin.
    """

    existing_user = db.query(User).filter(
        User.email == student_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    new_student = User(
        full_name=student_data.full_name,
        email=student_data.email,
        password_hash=hash_password(student_data.password),
        role=UserRole.STUDENT.value,
        is_active=True
    )

    try:
        db.add(new_student)
        db.commit()
        db.refresh(new_student)

    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    return new_student


# -----------------------------------------
# USER LOGIN
# -----------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    login_data: LoginRequest,
    db: Session = Depends(get_db)
):
    """
    Allow Students, Examiners and Admins to log in.
    """

    user = db.query(User).filter(
        User.email == login_data.email
    ).first()

    if user is None or not verify_password(
        login_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Contact an Admin."
        )

    access_token = create_access_token(
        subject=str(user.id)
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
