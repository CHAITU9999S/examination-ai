from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


# -----------------------------------------
# USER ROLES
# -----------------------------------------

class UserRole(str, Enum):
    STUDENT = "student"
    EXAMINER = "examiner"
    ADMIN = "admin"


# -----------------------------------------
# COMMON BASE SCHEMA
# -----------------------------------------

class BaseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# -----------------------------------------
# STUDENT REGISTRATION
# -----------------------------------------

class StudentRegister(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


# -----------------------------------------
# LOGIN
# -----------------------------------------

class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


# -----------------------------------------
# TOKEN RESPONSE
# -----------------------------------------

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


# -----------------------------------------
# USER RESPONSE
# -----------------------------------------

class UserResponse(BaseSchema):
    id: int
    full_name: str
    email: EmailStr
    role: UserRole
    is_active: bool


# -----------------------------------------
# ADMIN USER CREATION
# Only Admins and Examiners can be
# created through the admin interface.
# -----------------------------------------

class AdminUserCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: UserRole


# -----------------------------------------
# USER ACCOUNT STATUS
# -----------------------------------------

class UserStatusUpdate(BaseModel):
    is_active: bool


# -----------------------------------------
# PASSWORD CHANGE
# -----------------------------------------

class PasswordChange(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


# -----------------------------------------
# GENERAL MESSAGE RESPONSE
# -----------------------------------------

class MessageResponse(BaseModel):
    message: str
