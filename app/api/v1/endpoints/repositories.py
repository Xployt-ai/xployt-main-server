from fastapi import APIRouter, Depends, HTTPException, Query
from typing import List
from motor.motor_asyncio import AsyncIOMotorDatabase
from bson import ObjectId

from app.api.deps import get_db, get_current_active_user_with_token
from app.models.user import UserInDB
from app.models.repository import Repository, RepositoryCreate, RepositoryWithLinkStatus, RepositoryBase
from app.models.common import RepositoryOperation, ApiResponse
from app.models.files import FileItem, FileContentResponse
from app.services.github import get_user_repos, get_repo_details_by_name
from app.services.git_service import git_service

router = APIRouter()

@router.get("/", response_model=ApiResponse[List[RepositoryWithLinkStatus]])
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

    return ApiResponse(data=repos_with_status, message="Repositories retrieved successfully")

@router.post("/", response_model=ApiResponse[Repository])
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

    repository = Repository(**created_repo)
    return ApiResponse(data=repository, message="Repository linked successfully")

@router.post("/{repo_name:path}/clone", response_model=ApiResponse[RepositoryOperation], status_code=201)
async def clone_repository(
    repo_name: str,
    db: AsyncIOMotorDatabase = Depends(get_db),
    current_user: UserInDB = Depends(get_current_active_user_with_token),
):
    """
    Clones a repository to the local file system.
    This implicitly checks for user's permission by using their token.
    """
    if not current_user.github_access_token:
        raise HTTPException(status_code=400, detail="GitHub token not found for user.")

    try:
        repo_details = await get_repo_details_by_name(
            current_user.github_access_token, repo_name
        )
        clone_url = repo_details["clone_url"]

        repo_path = git_service.clone_repository(
            repo_url=clone_url,
            repo_name=repo_name,
            access_token=current_user.github_access_token
        )
        operation = RepositoryOperation(
            message="Repository cloned successfully", 
            path=str(repo_path),
            repository_name=repo_name
        )
        return ApiResponse(data=operation)
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get repository details from GitHub: {e}")

@router.post("/{repo_name:path}/pull", response_model=ApiResponse[RepositoryOperation])
async def pull_repository_updates(
    repo_name: str,
    current_user: UserInDB = Depends(get_current_active_user_with_token),
):
    """
    Pulls the latest changes for a locally cloned repository.
    """
    try:
        repo_path = git_service.pull_repository(repo_name)
        operation = RepositoryOperation(
            message="Repository updated successfully", 
            path=str(repo_path),
            repository_name=repo_name
        )
        return ApiResponse(data=operation)
    except ValueError as e:
        # This is raised by our service if the repo isn't cloned yet.
        raise HTTPException(status_code=404, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e)) 

@router.get("/{repo_name:path}/tree", response_model=ApiResponse[FileItem])
async def get_repository_tree(
    repo_name: str,
    current_user: UserInDB = Depends(get_current_active_user_with_token),
):
    try:
        tree = git_service.get_repository_tree(repo_name)
        return ApiResponse(data=tree, message="Repository tree retrieved successfully")
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{repo_name:path}/file", response_model=ApiResponse[FileContentResponse])
async def get_file_content(
    repo_name: str,
    path: str = Query(..., description="Relative path to file within repository"),
    current_user: UserInDB = Depends(get_current_active_user_with_token),
):
    try:
        content = git_service.read_file_content(repo_name, path)
        return ApiResponse(data=content, message="File content retrieved successfully")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))