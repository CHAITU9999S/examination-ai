from fastapi import APIRouter, Depends, HTTPException, status
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
    LoginRequest,
    StudentRegister,
    TokenResponse,
    UserResponse,
)


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


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
    Public registration is restricted to Students.
    Admin and Examiner accounts cannot be created here.
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
        hashed_password=hash_password(student_data.password),
        role="student",
        is_active=True
    )

    db.add(new_student)
    db.commit()
    db.refresh(new_student)

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
    Login is available to Students, Examiners and Admins.
    """

    user = db.query(User).filter(
        User.email == login_data.email
    ).first()

    if user is None or not verify_password(
        login_data.password,
        user.hashed_password
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
