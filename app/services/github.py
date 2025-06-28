import httpx
from typing import List, Dict, Any

async def get_user_repos(token: str) -> List[Dict[str, Any]]:
    """
    Fetches a user's repositories from GitHub.
    """
    url = "https://api.github.com/user/repos"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params={"type": "all"})
        response.raise_for_status()
        return response.json()

async def get_repo_details_by_name(token: str, repo_name: str) -> Dict[str, Any]:
    """
    Fetches details for a specific repository from GitHub.
    repo_name should be in 'owner/repo' format.
    """
    url = f"https://api.github.com/repos/{repo_name}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()  # Will raise an exception for 4xx/5xx responses
        return response.json() 