"""Service for ChromaDB operations (store, query, list, delete)."""

import logging
from datetime import datetime, timezone

import chromadb

from app.config import CHROMA_PERSIST_DIR

logger = logging.getLogger(__name__)

_client = chromadb.PersistentClient(path=CHROMA_PERSIST_DIR)


def _get_collection(repo_id: str) -> chromadb.Collection:
    """Get or create a ChromaDB collection for a repository."""
    return _client.get_or_create_collection(
        name=repo_id,
        metadata={"hnsw:space": "cosine"},
    )


def repo_exists(repo_id: str) -> bool:
    """Check whether a collection for the given repo_id exists in ChromaDB."""
    existing = {col.name for col in _client.list_collections()}
    return repo_id in existing


def store_chunks(
    repo_id: str,
    chunks: list[dict],
    embeddings: list[list[float]],
) -> None:
    """Store code chunks and their embeddings in ChromaDB.

    Creates (or replaces) a collection for the given repo and upserts
    all chunks with their embeddings and metadata.

    Args:
        repo_id: UUID string identifying the repository.
        chunks: List of chunk dicts from chunker.py.
        embeddings: Corresponding embedding vectors (same order as chunks).
    """
    collection = _get_collection(repo_id)

    # ChromaDB upsert has a practical batch limit — process in groups of 500
    batch_size = 500
    for i in range(0, len(chunks), batch_size):
        batch_chunks = chunks[i : i + batch_size]
        batch_embeddings = embeddings[i : i + batch_size]

        collection.upsert(
            ids=[c["chunk_id"] for c in batch_chunks],
            documents=[c["content"] for c in batch_chunks],
            embeddings=batch_embeddings,
            metadatas=[
                {
                    "filename": c["filename"],
                    "start_line": c["start_line"],
                    "end_line": c["end_line"],
                    "language": c["language"],
                    "indexed_at": datetime.now(timezone.utc).isoformat(),
                }
                for c in batch_chunks
            ],
        )

    logger.info(
        "Stored %d chunks for repo %s", len(chunks), repo_id,
    )


def query_chunks(
    repo_id: str,
    query_embedding: list[float],
    top_k: int = 8,
) -> list[dict]:
    """Query ChromaDB for the most relevant chunks.

    Args:
        repo_id: UUID string identifying the repository.
        query_embedding: Embedding vector for the user's question.
        top_k: Number of top results to return (default 8).

    Returns:
        List of dicts sorted by relevance, each containing:
        content, filename, start_line, end_line, language, score.
    """
    collection = _get_collection(repo_id)

    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"],
    )

    chunks: list[dict] = []
    # ChromaDB returns lists-of-lists (one per query); we only send one query
    documents = results["documents"][0]
    metadatas = results["metadatas"][0]
    distances = results["distances"][0]

    for doc, meta, distance in zip(documents, metadatas, distances):
        # ChromaDB cosine distance = 1 - cosine_similarity
        score = 1.0 - distance
        chunks.append({
            "content": doc,
            "filename": meta["filename"],
            "start_line": meta["start_line"],
            "end_line": meta["end_line"],
            "language": meta["language"],
            "score": round(score, 4),
        })

    return chunks


def list_repos() -> list[dict]:
    """List all indexed repositories stored in ChromaDB.

    Returns:
        List of dicts with repo_id, name, chunks, indexed_at.
    """
    collections = _client.list_collections()
    repos: list[dict] = []

    for col in collections:
        count = col.count()
        # Peek at one document to grab the indexed_at timestamp
        peek = col.peek(limit=1)
        indexed_at = ""
        if peek["metadatas"]:
            indexed_at = peek["metadatas"][0].get("indexed_at", "")

        # Collect unique filenames to report file count
        all_meta = col.get(include=["metadatas"])
        unique_files = {m["filename"] for m in all_meta["metadatas"]} if all_meta["metadatas"] else set()

        repos.append({
            "repo_id": col.name,
            "name": col.name,
            "files": len(unique_files),
            "chunks": count,
            "indexed_at": indexed_at,
        })

    return repos


def delete_repo(repo_id: str) -> None:
    """Delete a repository's collection from ChromaDB.

    Args:
        repo_id: UUID string identifying the repository to remove.
    """
    _client.delete_collection(name=repo_id)
    logger.info("Deleted collection for repo %s", repo_id)
