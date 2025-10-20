from pathlib import Path
import subprocess
from app.core.config import settings
from typing import Set, List
import mimetypes

from app.models.files import FileItem, FileContentResponse

from app.models.user import UserInDB
from app.services.github import get_repo_details_by_name

class GitService:
    def __init__(self, base_path: Path = settings.REPOS_STORAGE_PATH):
        self.base_path = base_path
        if not self.base_path.exists():
            self.base_path.mkdir(parents=True, exist_ok=True)

    def get_repo_path(self, repo_name: str) -> Path:
        """Constructs the local path for a given repository."""
        # TODO: multi-tenancy
        return self.base_path / repo_name.replace("/", "_")

    def get_absolute_repo_path_str(self, repo_name: str) -> str:
        return str(self.get_repo_path(repo_name).resolve())

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

    def count_repo_loc(self, repo_name: str) -> int:
        """Count lines of code in a locally cloned repository.

        Skips common vendor/build/cache directories and counts only common code file extensions.
        """
        repo_path = self.get_repo_path(repo_name)
        if not repo_path.exists():
            raise ValueError("Repository not found locally. It must be cloned first.")

        skip_dirs: Set[str] = {
            ".git", "node_modules", "venv", ".venv", "dist", "build", "__pycache__",
            ".idea", ".vscode", "target", "out"
        }
        exts: Set[str] = {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".go", ".rs", ".java", ".kt",
            ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".scala",
            ".sh", ".yml", ".yaml", ".toml", ".ini"
        }

        total = 0
        for path in repo_path.rglob("*"):
            if not path.is_file():
                continue

            # Skip files inside excluded directories
            if any(part in skip_dirs for part in path.parts):
                continue

            if path.suffix.lower() not in exts:
                continue

            try:
                with path.open("r", encoding="utf-8", errors="ignore") as f:
                    for _ in f:
                        total += 1
            except Exception:
                # Ignore unreadable files
                continue

        return total

    def _build_tree(self, path: Path) -> FileItem:
        if path.is_dir():
            children: List[FileItem] = []
            for child in sorted(path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                if child.name == ".git":
                    continue
                children.append(self._build_tree(child))
            return FileItem(name=path.name, type="folder", children=children)
        return FileItem(name=path.name, type="file")

    def get_repository_tree(self, repo_name: str) -> FileItem:
        repo_path = self.get_repo_path(repo_name)
        if not repo_path.exists():
            raise ValueError("Repository not found locally. It must be cloned first.")
        return self._build_tree(repo_path)

    def _guess_language(self, path: Path) -> str:
        ext = path.suffix.lower()
        mapping = {
            ".py": "python",
            ".js": "javascript",
            ".ts": "typescript",
            ".tsx": "tsx",
            ".jsx": "jsx",
            ".go": "go",
            ".rs": "rust",
            ".java": "java",
            ".kt": "kotlin",
            ".c": "c",
            ".h": "c",
            ".cpp": "cpp",
            ".hpp": "cpp",
            ".cs": "csharp",
            ".rb": "ruby",
            ".php": "php",
            ".swift": "swift",
            ".scala": "scala",
            ".sh": "bash",
            ".yml": "yaml",
            ".yaml": "yaml",
            ".json": "json",
            ".toml": "toml",
            ".ini": "ini",
            ".md": "markdown",
        }
        return mapping.get(ext, (mimetypes.guess_type(str(path))[0] or "text/plain"))

    def read_file_content(self, repo_name: str, relative_path: str) -> FileContentResponse:
        repo_path = self.get_repo_path(repo_name)
        if not repo_path.exists():
            raise ValueError("Repository not found locally. It must be cloned first.")

        target_path = (repo_path / relative_path).resolve()
        if not str(target_path).startswith(str(repo_path.resolve())):
            raise ValueError("Invalid path.")
        if not target_path.exists() or not target_path.is_file():
            raise FileNotFoundError("File not found.")

        try:
            code = target_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            code = target_path.read_text(encoding="latin-1", errors="ignore")

        language = self._guess_language(target_path)
        return FileContentResponse(code=code, language=language)

    async def clone_github_repository(
        self,
        repo_name: str,
        current_user: UserInDB,
    ):
        """
        Clones a repository to the local file system.
        This implicitly checks for user's permission by using their token.
        """
        if not current_user.github_access_token:
            raise ValueError("GitHub token not found for user.")

        try:
            repo_details = await get_repo_details_by_name(
                current_user.github_access_token, repo_name
            )
            clone_url = repo_details["clone_url"]

            repo_path = self.clone_repository(
                repo_url=clone_url,
                repo_name=repo_name,
                access_token=current_user.github_access_token
            )
            return repo_path
        except RuntimeError as e:
            raise RuntimeError(f"Failed to clone repository: {e.stderr}")
        except Exception as e:
            raise Exception(f"Failed to get repository details from GitHub: {e}")

git_service = GitService() 