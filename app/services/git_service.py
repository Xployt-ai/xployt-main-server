from pathlib import Path
import subprocess
from app.core.config import settings

class GitService:
    def __init__(self, base_path: Path = settings.REPOS_STORAGE_PATH):
        self.base_path = base_path
        if not self.base_path.exists():
            self.base_path.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, repo_name: str) -> Path:
        """Constructs the local path for a given repository."""
        # TODO: multi-tenancy
        return self.base_path / repo_name.replace("/", "_")

    def clone_repository(self, repo_url: str, repo_name: str, access_token: str) -> Path:
        """
        Clones a repository using the user's access token.
        Example URL: https://[access_token]@github.com/user/repo.git
        """
        repo_path = self.get_repo_path(repo_name)
        if repo_path.exists():
          return repo_path

        # Add token to URL for private repos
        auth_repo_url = repo_url.replace("https://", f"https://{access_token}@")
        
        command = ["git", "clone", auth_repo_url, str(repo_path)]
        
        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            return repo_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr}")

    def pull_repository(self, repo_name: str) -> Path:
        """Pulls the latest changes for a repository."""
        repo_path = self.get_repo_path(repo_name)
        if not repo_path.exists():
            raise ValueError("Repository not found locally. It must be cloned first.")

        command = ["git", "-C", str(repo_path), "pull"]

        try:
            subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
            return repo_path
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Failed to pull repository: {e.stderr}")

git_service = GitService() 