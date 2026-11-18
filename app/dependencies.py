
import os
from typing import Callable

from fastapi import Depends, HTTPException, status
from fastapi.security import (
    HTTPAuthorizationCredentials,
    HTTPBearer,
)
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.schemas import UserRole


# -----------------------------------------
# JWT CONFIGURATION
# -----------------------------------------

JWT_SECRET_KEY = os.getenv(
    "JWT_SECRET_KEY",
    "development-only-secret-change-before-deployment"
)

JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")

bearer_scheme = HTTPBearer(auto_error=False)


# -----------------------------------------
# CURRENT AUTHENTICATED USER
# -----------------------------------------

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db)
) -> User:

    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            JWT_SECRET_KEY,
            algorithms=[JWT_ALGORITHM]
        )

        user_id = payload.get("sub")

        if user_id is None:
            raise ValueError("Token subject is missing")

        user_id = int(user_id)

    except (JWTError, ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    user = db.query(User).filter(
        User.id == user_id
    ).first()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account not found or inactive."
        )

    return user


# -----------------------------------------
# ROLE-BASED ACCESS CONTROL
# -----------------------------------------

def require_roles(*allowed_roles: UserRole) -> Callable:

    def role_checker(
        current_user: User = Depends(get_current_user)
    ) -> User:

        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource."
            )

        return current_user

    return role_checker


# Backward-compatible singular function name.
def require_role(*roles) -> Callable:

    normalized_roles = []

    for role in roles:
        try:
            normalized_roles.append(UserRole(role))
        except ValueError:
            raise ValueError(f"Unsupported user role: {role}")

    return require_roles(*normalized_roles)


# -----------------------------------------
# ROLE-SPECIFIC DEPENDENCIES
# -----------------------------------------

get_current_admin = require_roles(UserRole.ADMIN)

get_current_examiner = require_roles(UserRole.EXAMINER)

get_current_student = require_roles(UserRole.STUDENT)
        
