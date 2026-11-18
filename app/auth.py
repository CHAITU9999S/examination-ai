
import os
from datetime import datetime, timedelta, timezone
from typing import Optional

from jose import JWTError, jwt
from passlib.context import CryptContext


# -----------------------------------------
# AUTHENTICATION CONFIGURATION
# -----------------------------------------

JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "development-only-secret-change-before-deployment"
)

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

ACCESS_TOKEN_EXPIRE_MINUTES = int(
    os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30")
)


# -----------------------------------------
# PASSWORD HASHING
# -----------------------------------------

password_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)


def hash_password(password: str) -> str:
    """Hash a password before storing it in the database."""

    return password_context.hash(password)


def verify_password(
    plain_password: str,
    hashed_password: str
) -> bool:
    """Verify a submitted password against its stored hash."""

    return password_context.verify(
        plain_password,
        hashed_password
    )


# -----------------------------------------
# JWT ACCESS TOKEN CREATION
# -----------------------------------------

def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None
) -> str:
    """Create a signed JWT access token."""

    now = datetime.now(timezone.utc)

    if expires_delta is None:
        expires_delta = timedelta(
            minutes=ACCESS_TOKEN_EXPIRE_MINUTES
        )

    expire = now + expires_delta

    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": expire,
    }

    return jwt.encode(
        payload,
        JWT_SECRET_KEY,
        algorithm=JWT_ALGORITHM
    )


# -----------------------------------------
# JWT TOKEN VERIFICATION
# -----------------------------------------

def verify_token(token: str) -> Optional[dict]:
    """
    Decode and verify a JWT token.

    Returns the decoded payload when valid.
    Returns None when the token is invalid or expired.
    """

    try:
        return jwt.decode(
            token,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

    except JWTError:
        return None
            
