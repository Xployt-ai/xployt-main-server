from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
import httpx
from bson import ObjectId
from app.core.config import settings
from app.models.user import User, UserCreate, UserInDB
from app.core.security import create_access_token
from app.api.deps import get_db, get_current_user

router = APIRouter()

@router.get("/github")
async def github_login():
    return {
        "url": f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&redirect_uri={settings.GITHUB_CALLBACK_URL}&scope=repo user"
    }

@router.get("/github/callback")
async def github_callback(code: str, db = Depends(get_db)):
    async with httpx.AsyncClient() as client:
        token_response = await client.post(
            "https://github.com/login/oauth/access_token",
            json={
                "client_id": settings.GITHUB_CLIENT_ID,
                "client_secret": settings.GITHUB_CLIENT_SECRET,
                "code": code
            },
            headers={"Accept": "application/json"}
        )
        
        if token_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Could not get GitHub access token")
        
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        
        user_response = await client.get(
            "https://api.github.com/user",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json"
            }
        )
        
        if user_response.status_code != 200:
            raise HTTPException(status_code=400, detail="Could not get GitHub user data")
        
        user_data = user_response.json()
        
        user = await db["users"].find_one({"github_id": str(user_data["id"])})
        
        if not user:
            new_user = UserCreate(
                github_id=str(user_data["id"]),
                username=user_data["login"],
                email=user_data.get("email"),
                avatar_url=user_data.get("avatar_url"),
                github_access_token=access_token
            )
            
            result = await db["users"].insert_one(new_user.model_dump())
            user_id = str(result.inserted_id)
        else:
            user_id = str(user["_id"])
            await db["users"].update_one(
                {"_id": user["_id"]},
                {"$set": {"github_access_token": access_token}}
            )
        
        jwt_token = create_access_token(data={"sub": user_id})
        
        # TODO: Implement frontend redirect with proper token handling
        # For now, return token in response
        return {"access_token": jwt_token, "token_type": "bearer"}

@router.get("/me", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user 