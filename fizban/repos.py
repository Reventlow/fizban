"""Git repository management."""

import logging
import subprocess
from pathlib import Path

from fizban.config import Config, get_config

logger = logging.getLogger(__name__)


def pull_all(config: Config | None = None) -> dict[str, str]:
    """Pull latest changes from all configured repos.

    Returns:
        Dict mapping repo path to result message ("ok", "error: ...", "skipped: not a git repo").
    """
    config = config or get_config()
    results = {}
    for repo_path in config.repos:
        path = Path(repo_path)
        if not path.exists():
            results[repo_path] = "error: path does not exist"
            continue
        if not (path / ".git").exists():
            results[repo_path] = "skipped: not a git repo"
            continue
        try:
            result = subprocess.run(
                ["git", "-C", str(path), "pull", "--ff-only"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode == 0:
                results[repo_path] = "ok"
                logger.info("Pulled %s: %s", repo_path, result.stdout.strip())
            else:
                results[repo_path] = f"error: {result.stderr.strip()}"
                logger.warning(
                    "Failed to pull %s: %s", repo_path, result.stderr.strip()
                )
        except subprocess.TimeoutExpired:
            results[repo_path] = "error: timeout"
        except Exception as e:
            results[repo_path] = f"error: {e}"
    return results


def scan_repo(repo_path: str) -> list[Path]:
    """Find all markdown files in a repository.

    Args:
        repo_path: Absolute path to the repository root.

    Returns:
        Sorted list of absolute paths to .md files.
    """
    path = Path(repo_path)
    if not path.exists():
        logger.warning("Repo path does not exist: %s", repo_path)
        return []
    md_files = sorted(path.rglob("*.md"))
    logger.info("Found %d markdown files in %s", len(md_files), repo_path)
    return md_files
