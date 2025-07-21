from fastapi import APIRouter
from app.api.v1.endpoints import auth, repositories, credits, users

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])
api_router.include_router(users.router, prefix="/users", tags=["users"]) 