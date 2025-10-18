from fastapi import APIRouter

from app.api.v1.endpoints import auth, repositories, credits, scans, users, scan_collections

api_router = APIRouter()
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(repositories.router, prefix="/repositories", tags=["repositories"])
api_router.include_router(credits.router, prefix="/credits", tags=["credits"])
api_router.include_router(scans.router, prefix="/scans", tags=["scans"]) 
api_router.include_router(users.router, prefix="/users", tags=["users"]) 
api_router.include_router(scan_collections.router, prefix="/scan-collections", tags=["scan-collections"]) 

