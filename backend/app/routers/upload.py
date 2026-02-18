"""Router for repository upload and indexing."""

import logging
import uuid

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.github import clone_repo, cleanup_repo
from app.services.chunker import chunk_repository
from app.services.embedder import embed_texts
from app.services.vectorstore import store_chunks

logger = logging.getLogger(__name__)

router = APIRouter()


class UploadRequest(BaseModel):
    github_url: str


class UploadResponse(BaseModel):
    repo_id: str
    repo_name: str
    files_processed: int
    chunks_created: int
    status: str


@router.post("/upload", response_model=UploadResponse)
async def upload_repo(body: UploadRequest):
    """Clone a GitHub repo, chunk its code, embed, and store in ChromaDB.

    Full pipeline: clone → chunk → embed → store → cleanup.
    """
    repo_path: str | None = None

    try:
        # 1. Clone
        repo_path = await clone_repo(body.github_url)
        repo_name = repo_path.split("/")[-1]
        repo_id = f"{repo_name}-{uuid.uuid4().hex[:8]}"

        # 2. Chunk
        chunks = chunk_repository(repo_path, repo_id)
        if not chunks:
            raise HTTPException(
                status_code=400,
                detail="No code files found in repository.",
            )

        # 3. Embed
        texts = [c["content"] for c in chunks]
        embeddings = await embed_texts(texts)

        # 4. Store
        store_chunks(repo_id, chunks, embeddings)

        # 5. Compute stats
        unique_files = {c["filename"] for c in chunks}

        return UploadResponse(
            repo_id=repo_id,
            repo_name=repo_name,
            files_processed=len(unique_files),
            chunks_created=len(chunks),
            status="indexed",
        )

    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
    except RuntimeError as e:
        logger.exception("Upload failed")
        raise HTTPException(status_code=502, detail=str(e)) from e
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Unexpected error during upload")
        raise HTTPException(status_code=500, detail=str(e)) from e
    finally:
        if repo_path:
            cleanup_repo(repo_path)
