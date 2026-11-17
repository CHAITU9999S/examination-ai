
import os
import secrets

from fastapi import (
    APIRouter,
    Depends,
    Header,
    HTTPException,
    status
)
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import require_role
from app.models import User
from app.schemas import UserCreate, UserResponse, UserLogin
from app.admin_schemas import AdminAccountCreate
from app.auth import (
    hash_password,
    verify_password,
    create_access_token
)
from app.services.admin_service import record_admin_activity


router = APIRouter(
    prefix="/auth",
    tags=["Authentication"]
)


# --------------------------------------------------
# 1. STUDENT REGISTRATION
# --------------------------------------------------

@router.post("/register", response_model=UserResponse)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    new_user = User(
        full_name=user_data.full_name,
        email=user_data.email,
        department=user_data.department,
        password_hash=hash_password(user_data.password),
        role="student"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# --------------------------------------------------
# 2. LOGIN
# --------------------------------------------------

@router.post("/login")
def login(
    user_data: UserLogin,
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if not user or not verify_password(
        user_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is inactive"
        )

    token = create_access_token({
        "sub": str(user.id)
    })

    return {
        "access_token": token,
        "token_type": "bearer"
    }


# --------------------------------------------------
# 3. ADMIN CREATES EXAMINER
# --------------------------------------------------

@router.post(
    "/create-examiner",
    response_model=UserResponse
)
def create_examiner(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_role("admin"))
):
    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    examiner = User(
        full_name=user_data.full_name,
        email=user_data.email,
        department=user_data.department,
        password_hash=hash_password(user_data.password),
        role="examiner",
        is_active=True
    )

    db.add(examiner)
    db.flush()

    record_admin_activity(
        db=db,
        actor_user_id=current_user.id,
        target_user_id=examiner.id,
        action="created_examiner_account",
        details={
            "created_email": examiner.email,
            "created_role": "examiner"
        }
    )

    db.commit()
    db.refresh(examiner)

    return examiner


# --------------------------------------------------
# 4. SECURE INITIAL ADMIN CREATION
# --------------------------------------------------

@router.post(
    "/bootstrap-admin",
    response_model=UserResponse
)
def bootstrap_admin(
    user_data: AdminAccountCreate,
    bootstrap_secret: str = Header(
        ...,
        alias="X-Admin-Bootstrap-Secret"
    ),
    db: Session = Depends(get_db)
):
    expected_secret = os.getenv(
        "ADMIN_BOOTSTRAP_SECRET"
    )

    if not expected_secret or len(expected_secret) < 32:
        raise HTTPException(
            status_code=503,
            detail="Admin setup is not configured securely"
        )

    if not secrets.compare_digest(
        bootstrap_secret,
        expected_secret
    ):
        raise HTTPException(
            status_code=403,
            detail="Invalid setup secret"
        )

    # Prevent simultaneous bootstrap requests on PostgreSQL.
    if db.get_bind().dialect.name == "postgresql":
        db.execute(
            text("SELECT pg_advisory_xact_lock(741923610)")
        )

    existing_admin = db.query(User).filter(
        User.role == "admin"
    ).first()

    if existing_admin:
        raise HTTPException(
            status_code=409,
            detail="Admin setup is already completed"
        )

    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=400,
            detail="Email already registered"
        )

    admin = User(
        full_name=user_data.full_name,
        email=user_data.email,
        department=user_data.department,
        password_hash=hash_password(user_data.password),
        role="admin",
        is_active=True
    )

    db.add(admin)
    db.flush()

    record_admin_activity(
        db=db,
        actor_user_id=admin.id,
        target_user_id=admin.id,
        action="bootstrapped_initial_admin",
        details={
            "created_role": "admin",
            "creation_method": "secure_bootstrap"
        }
    )

    db.commit()
    db.refresh(admin)

    return admin
