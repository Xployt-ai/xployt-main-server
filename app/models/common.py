from typing import Optional, Any, Generic, TypeVar
from pydantic import BaseModel, Field
from datetime import datetime

T = TypeVar('T')

class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: T
    message: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class ApiError(BaseModel):
    success: bool = False
    error: str
    detail: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)

class SuccessMessage(BaseModel):
    message: str
    details: Optional[dict[str, Any]] = None

class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class GitHubAuthUrl(BaseModel):
    url: str

class RepositoryOperation(BaseModel):
    message: str
    path: str
    repository_name: Optional[str] = None

class CreditBalanceResponse(BaseModel):
    balance: Any
    user_id: str
    last_updated: Optional[datetime] = None 