
from datetime import datetime, timedelta, timezone
import os

from jose import jwt
from passlib.context import CryptContext


SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY environment variable is required"
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
EXAM_TOKEN_GRACE_MINUTES = 5

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    return pwd_context.verify(
        plain_password,
        hashed_password
    )


def create_access_token(
    data: dict,
    expires_delta=None
) -> str:
    to_encode = data.copy()

    # Normal login tokens are access tokens.
    # Exam tokens retain their separate exam type.
    to_encode.setdefault("token_type", "access")

    expire = datetime.now(timezone.utc) + (
        expires_delta
        or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM
    )


def verify_token(token: str):
    try:
        return jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM]
        )
    except Exception:
        return None


def create_exam_access_token(
    exam_id: int,
    student_id: int,
    session_id: int,
    expires_at: datetime
) -> str:
    # Database DateTime values may be timezone-naive.
    if expires_at.tzinfo is None:
        session_deadline = expires_at.replace(
            tzinfo=timezone.utc
        )
    else:
        session_deadline = expires_at.astimezone(
            timezone.utc
        )

    now = datetime.now(timezone.utc)

    # The token expires shortly after the session deadline.
    # The database session deadline remains authoritative.
    expires_delta = (
        session_deadline
        - now
        + timedelta(minutes=EXAM_TOKEN_GRACE_MINUTES)
    )

    token_data = {
        "sub": str(student_id),
        "exam_id": exam_id,
        "student_id": student_id,
        "session_id": session_id,
        "token_type": "exam"
    }

    return create_access_token(
        token_data,
        expires_delta=expires_delta
    )
    
