"""Service for cloning/downloading repositories from GitHub."""

import asyncio
import re
import shutil
import tempfile
from pathlib import Path


async def clone_repo(github_url: str) -> str:
    """Shallow-clone a GitHub repository to a temporary directory.

    Args:
        github_url: Full GitHub repository URL
                    (e.g. "https://github.com/user/repo").

    Returns:
        Path to the cloned repository on disk.

    Raises:
        ValueError: If the URL doesn't look like a valid GitHub repo URL.
        RuntimeError: If the git clone subprocess fails.
    """
    pattern = r"^https://github\.com/[\w\-\.]+/[\w\-\.]+/?$"
    if not re.match(pattern, github_url.strip()):
        raise ValueError(f"Invalid GitHub URL: {github_url}")

    # Strip trailing slash and extract repo name
    url = github_url.strip().rstrip("/")
    repo_name = url.split("/")[-1].removesuffix(".git")

    tmp_dir = tempfile.mkdtemp(prefix="repopilot_")
    dest = str(Path(tmp_dir) / repo_name)

    proc = await asyncio.create_subprocess_exec(
        "git", "clone", "--depth", "1", url, dest,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()

    if proc.returncode != 0:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        raise RuntimeError(f"git clone failed: {stderr.decode().strip()}")

    return dest


def cleanup_repo(repo_path: str) -> None:
    """Remove a previously cloned repository from disk.

    Args:
        repo_path: Path returned by clone_repo.
    """
    # Walk up to the temp parent dir (repopilot_*) so we clean everything
    parent = str(Path(repo_path).parent)
    shutil.rmtree(parent, ignore_errors=True)
