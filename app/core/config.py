from typing import Optional
from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    PROJECT_NAME: str = "Xploit.ai"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    
    MONGODB_URL: str
    MONGODB_NAME: str = "xploitai"
    
    GITHUB_CLIENT_ID: str
    GITHUB_CLIENT_SECRET: str
    GITHUB_CALLBACK_URL: str = "http://localhost:8000/api/v1/auth/github/callback"
    
    REPOS_STORAGE_PATH: Path = Path("local_storage/repos")
    
    class Config:
        env_file = ".env"

settings = Settings() 