from typing import Optional
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime

# Base user model with common attributes
class UserBase(BaseModel):
    github_id: Optional[str] = None
    username: str
    email: Optional[EmailStr] = None
    avatar_url: Optional[str] = None

# Model for creating new users with access token
class UserCreate(UserBase):
    github_access_token: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Internal database model with sensitive data
class UserInDB(UserBase):
    id: Optional[str] = None
    github_access_token: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# Public-facing user model without sensitive data
class User(UserBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True