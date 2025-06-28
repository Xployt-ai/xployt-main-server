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