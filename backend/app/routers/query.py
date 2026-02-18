"""Router for querying indexed repositories."""

import json
import logging

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.limiter import limiter
from app.services.embedder import embed_texts
from app.services.vectorstore import query_chunks, repo_exists
from app.services.llm import stream_response

logger = logging.getLogger(__name__)

router = APIRouter()


class QueryRequest(BaseModel):
    repo_id: str
    question: str


@router.post("/query")
@limiter.limit("30/hour")
async def query_repo(request: Request, body: QueryRequest):
    """Embed the question, retrieve relevant chunks, and stream Claude's answer.

    Returns a Server-Sent Events stream:
        1. {"type": "sources", "chunks": [...]}
        2. {"type": "token", "content": "..."} (repeated)
        3. {"type": "done"}
    """
    # 1. Check repo exists before doing any work
    if not repo_exists(body.repo_id):
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    # 2. Embed the question
    try:
        embeddings = await embed_texts([body.question])
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e

    query_embedding = embeddings[0]

    # 3. Retrieve relevant chunks
    try:
        chunks = query_chunks(body.repo_id, query_embedding, top_k=8)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=f"Vector store error: {e}",
        ) from e

    if not chunks:
        raise HTTPException(
            status_code=404,
            detail="Repository not found",
        )

    # 3. Stream the response as SSE
    return StreamingResponse(
        _sse_generator(body.question, chunks),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


async def _sse_generator(question: str, chunks: list[dict]):
    """Yield SSE-formatted events: sources, tokens, done."""
    # First event: source chunks with content for collapsible display
    sources = [
        {
            "filename": c["filename"],
            "start_line": c["start_line"],
            "end_line": c["end_line"],
            "content": c["content"],
            "score": c["score"],
        }
        for c in chunks
    ]
    yield f"data: {json.dumps({'type': 'sources', 'chunks': sources})}\n\n"

    # Stream tokens from Claude
    try:
        async for token in stream_response(question, chunks):
            yield f"data: {json.dumps({'type': 'token', 'content': token})}\n\n"
    except RuntimeError as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    # Final event
    yield f"data: {json.dumps({'type': 'done'})}\n\n"
