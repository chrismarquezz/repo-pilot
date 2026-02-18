"""Router for listing and deleting indexed repositories."""

from fastapi import APIRouter, HTTPException

from app.services.vectorstore import list_repos, delete_repo, repo_exists

router = APIRouter()


@router.get("/repos")
async def get_repos():
    """Return all previously indexed repositories."""
    repos = list_repos()
    return {"repos": repos}


@router.delete("/repos/{repo_id}")
async def remove_repo(repo_id: str):
    """Delete an indexed repository from ChromaDB."""
    if not repo_exists(repo_id):
        raise HTTPException(status_code=404, detail="Repository not found")

    delete_repo(repo_id)
    return {"status": "deleted", "repo_id": repo_id}
