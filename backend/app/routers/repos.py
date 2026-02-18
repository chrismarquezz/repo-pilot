"""Router for listing indexed repositories."""

from fastapi import APIRouter

from app.services.vectorstore import list_repos

router = APIRouter()


@router.get("/repos")
async def get_repos():
    """Return all previously indexed repositories."""
    repos = list_repos()
    return {"repos": repos}
