from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime

class RepositoryBase(BaseModel):
    github_repo_id: str
    name: str
    private: bool

class RepositoryCreate(RepositoryBase):
    user_id: str
    webhook_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class RepositoryInDB(RepositoryBase):
    id: str
    user_id: str
    webhook_id: Optional[str] = None
    created_at: datetime

class Repository(RepositoryBase):
    id: str
    user_id: str
    webhook_id: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class RepositoryWithLinkStatus(RepositoryBase):
    is_linked: bool 