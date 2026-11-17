
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class AdminAccountCreate(BaseModel):
    full_name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    department: Optional[str] = Field(default=None, max_length=100)
    password: str = Field(min_length=8, max_length=128)

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "full_name": "System Administrator",
                "email": "admin@example.com",
                "department": "Administration",
                "password": "ReplaceWithYourStrongPassword123!"
            }
        }
    )


class UserStatusUpdate(BaseModel):
    is_active: bool
    
