import hmac
import os
import secrets

from fastapi import APIRouter, Depends, Header, HTTPException, Request, status
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    hash_password,
    verify_password,
)
from app.database import get_db
from app.models import ExamSession, LoginHistory, User
from app.schemas import (
    InitialAdminBootstrapRequest,
    LoginRequest,
    StudentRegister,
    TokenResponse,
    UserResponse,
    UserRole,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# -----------------------------------------
# REUSABLE ADMIN CREATION WITH SERVER SECRET
# -----------------------------------------

@router.post(
    "/bootstrap-admin",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def create_admin_with_setup_secret(
    admin_data: InitialAdminBootstrapRequest,
    setup_token: str | None = Header(
        default=None,
        alias="X-Admin-Bootstrap-Token"
    ),
    db: Session = Depends(get_db)
):
    """
    Create an Admin without a user login.

    This endpoint can create additional Admin accounts at any time.
    It is enabled only when ADMIN_BOOTSTRAP_SECRET is configured on
    the backend and every request supplies the matching secret header.
    """

    configured_token = os.getenv("ADMIN_BOOTSTRAP_SECRET")

    # Keep the endpoint unavailable unless a strong server-side secret exists.
    if not configured_token:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Not found."
        )

    if len(configured_token) < 32:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Admin creation is not securely configured."
        )

    if not setup_token or not hmac.compare_digest(
        setup_token,
        configured_token
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid Admin creation token."
        )

    normalized_email = str(admin_data.email).strip().lower()

    existing_user = db.query(User).filter(
        func.lower(User.email) == normalized_email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    new_admin = User(
        full_name=admin_data.full_name.strip(),
        email=normalized_email,
        password_hash=hash_password(admin_data.password),
        role=UserRole.ADMIN.value,
        is_active=True,
    )

    try:
        db.add(new_admin)
        db.commit()
        db.refresh(new_admin)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    return new_admin


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

    normalized_email = str(student_data.email).strip().lower()

    existing_user = db.query(User).filter(
        func.lower(User.email) == normalized_email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    new_student = User(
        full_name=student_data.full_name,
        email=normalized_email,
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
    request: Request,
    db: Session = Depends(get_db)
):
    """
    Allow Students, Examiners and Admins to log in.
    """

    normalized_email = str(login_data.email).strip().lower()

    user = db.query(User).filter(
        func.lower(User.email) == normalized_email
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

    # Serialize concurrent logins for this account. On PostgreSQL, the row
    # lock ensures the last committed login is the only active device.
    user = db.query(User).filter(
        User.id == user.id
    ).with_for_update().populate_existing().one()

    # Re-check account state and password after acquiring the lock so an
    # account deactivation or password change racing with login is respected.
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your account is inactive. Contact an Admin."
        )

    if not verify_password(login_data.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    active_session_id = secrets.token_urlsafe(32)
    user.active_session_id = active_session_id

    # Exam papers and saved answers remain untouched. Only credentials issued
    # to the previous device are revoked; a new device can resume the same
    # in-progress exam and receive fresh exam credentials.
    db.query(ExamSession).filter(
        ExamSession.student_id == user.id,
        ExamSession.status == "in_progress",
    ).update(
        {ExamSession.exam_token_refresh_hash: None},
        synchronize_session=False,
    )
    client_ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    db.add(LoginHistory(
        user_id=user.id,
        ip_address=client_ip[:45] if client_ip else None,
        user_agent=user_agent[:500] if user_agent else None,
    ))
    db.commit()

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "auth_session_id": active_session_id,
        }
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )
