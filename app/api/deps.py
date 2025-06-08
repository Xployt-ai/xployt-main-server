from typing import Generator, Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from bson import ObjectId
from app.core.security import verify_token
from app.models.user import User
from motor.motor_asyncio import AsyncIOMotorDatabase
from fastapi import Request

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

async def get_db(request: Request) -> AsyncIOMotorDatabase:
    return request.app.mongodb

async def get_current_user(
    db: AsyncIOMotorDatabase = Depends(get_db),
    token: str = Depends(oauth2_scheme)
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    user_id = verify_token(token)
    if not user_id:
        raise credentials_exception
        
    user = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise credentials_exception
    
    user["id"] = str(user["_id"])
    return User(**user) 