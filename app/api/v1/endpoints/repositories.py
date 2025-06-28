from fastapi import APIRouter, Depends, HTTPException
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.api.deps import get_db, get_current_active_user_with_token
from app.models.user import UserInDB
from app.models.repository import Repository, RepositoryCreate, RepositoryWithLinkStatus, RepositoryBase
from app.services.github import get_user_repos

router = APIRouter()

@router.get("/", response_model=List[RepositoryWithLinkStatus])
async def list_user_repositories(
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user_with_token),
):
    """
    List all of the user's GitHub repositories and show which ones are linked.
    """
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub token not found for user.")

    try:
        github_repos = await get_user_repos(current_user.github_access_token)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch repositories from GitHub: {e}")

    linked_repos_cursor = db["repositories"].find({"user_id": current_user.id})
    linked_repos_list = await linked_repos_cursor.to_list(length=None)
    linked_repo_ids = {repo["github_repo_id"] for repo in linked_repos_list}

    repos_with_status = []
    for repo in github_repos:
        repo_data = {
            "github_repo_id": str(repo["id"]),
            "name": repo["full_name"],
            "private": repo["private"],
            "is_linked": str(repo["id"]) in linked_repo_ids,
        }
        repos_with_status.append(RepositoryWithLinkStatus(**repo_data))

    return repos_with_status

@router.post("/", response_model=Repository)
async def link_repository(
    repo_to_link: RepositoryBase,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user_with_token),
):
    """
    Link a GitHub repository to the user's account.
    """
    existing_repo = await db["repositories"].find_one(
        {"github_repo_id": repo_to_link.github_repo_id, "user_id": current_user.id}
    )
    if existing_repo:
        raise HTTPException(status_code=400, detail="Repository is already linked.")

    repo_create = RepositoryCreate(
        **repo_to_link.model_dump(),
        user_id=current_user.id
    )

    inserted_repo = await db["repositories"].insert_one(repo_create.model_dump())
    
    created_repo = await db["repositories"].find_one({"_id": inserted_repo.inserted_id})
    created_repo["id"] = str(created_repo["_id"])

    return Repository(**created_repo) 