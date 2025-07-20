from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
import httpx
from bson import ObjectId
from app.core.config import settings
from app.models.user import User, UserCreate, UserInDB
from app.models.credit import UserCreditBalance
from app.models.common import GitHubAuthUrl, AuthResponse, ApiResponse
from app.core.security import create_access_token
from app.api.deps import get_db, get_current_user

router = APIRouter()

@router.get("/github", response_model=ApiResponse[GitHubAuthUrl], summary="Get GitHub OAuth login URL", response_description="Returns the GitHub OAuth authorization URL for user login")
async def github_login():
    """
    Get the GitHub OAuth login URL.
    
    Returns:
        ApiResponse[GitHubAuthUrl]: Contains the GitHub OAuth authorization URL
    """
    auth_url = GitHubAuthUrl(
        url=f"https://github.com/login/oauth/authorize?client_id={settings.GITHUB_CLIENT_ID}&redirect_uri={settings.GITHUB_CALLBACK_URL}&scope=repo user"
    )
    return ApiResponse(data=auth_url, message="GitHub OAuth URL generated successfully")

@router.get("/github/callback", response_model=ApiResponse[AuthResponse], summary="Handle GitHub OAuth callback", response_description="Returns JWT access token after successful GitHub authentication")
async def github_callback(code: str, db = Depends(get_db)):
    """
    Handle the GitHub OAuth callback after successful authentication.
    
    Args:
        code (str): The authorization code received from GitHub
        db: Database dependency
        
    Returns:
        ApiResponse[AuthResponse]: Contains access_token and token_type
        
    Raises:
        HTTPException: If GitHub token or user data retrieval fails
    """
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
            
            # Initialize credit balance for new user
            credit_balance = UserCreditBalance(user_id=user_id)
            await db["user_credits"].insert_one(credit_balance.model_dump())
        else:
            user_id = str(user["_id"])
            await db["users"].update_one(
                {"_id": user["_id"]},
                {"$set": {"github_access_token": access_token}}
            )
        
        jwt_token = create_access_token(data={"sub": user_id})
        
        auth_response = AuthResponse(access_token=jwt_token, token_type="bearer")
        return ApiResponse(data=auth_response, message="Authentication successful")

@router.get("/me", response_model=ApiResponse[User], summary="Get current user information", response_description="Returns the current authenticated user's information")
async def read_users_me(current_user: User = Depends(get_current_user)):
    """
    Get the current authenticated user's information.
    
    Args:
        current_user (User): Current authenticated user dependency
        
    Returns:
        ApiResponse[User]: Current user's data
    """
    return ApiResponse(data=current_user, message="User information retrieved successfully")