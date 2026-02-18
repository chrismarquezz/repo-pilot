"""RepoPilot performance benchmark.

Measures real indexing and query latencies against a live repository.
Requires ANTHROPIC_API_KEY and OPENAI_API_KEY in .env.

Usage:
    python benchmark.py
"""

import asyncio
import time
import uuid

from app.services.github import clone_repo, cleanup_repo
from app.services.chunker import chunk_repository, ALLOWED_EXTENSIONS
from app.services.embedder import embed_texts
from app.services.vectorstore import store_chunks, query_chunks, delete_repo
from app.services.llm import stream_response

REPO_URL = "https://github.com/chrismarquezz/chesslab"

QUESTIONS = [
    "How does the chess engine evaluate board positions?",
    "What move generation logic is used and where is it implemented?",
    "How does the UI render the chessboard?",
]


async def bench_indexing() -> tuple[str, str, int, int, dict[str, float]]:
    """Index the repo and return (repo_id, repo_path, files, chunks, timings)."""
    timings: dict[str, float] = {}

    # Clone
    t0 = time.perf_counter()
    repo_path = await clone_repo(REPO_URL)
    timings["clone"] = time.perf_counter() - t0

    repo_name = repo_path.split("/")[-1]
    repo_id = f"bench-{repo_name}-{uuid.uuid4().hex[:8]}"

    # Chunk
    t0 = time.perf_counter()
    chunks = chunk_repository(repo_path, repo_id)
    timings["chunk"] = time.perf_counter() - t0

    # Embed
    texts = [c["content"] for c in chunks]
    t0 = time.perf_counter()
    embeddings = await embed_texts(texts)
    timings["embed"] = time.perf_counter() - t0

    # Store
    t0 = time.perf_counter()
    store_chunks(repo_id, chunks, embeddings)
    timings["store"] = time.perf_counter() - t0

    timings["total"] = sum(timings.values())

    unique_files = {c["filename"] for c in chunks}
    return repo_id, repo_path, len(unique_files), len(chunks), timings


async def bench_query(
    repo_id: str, question: str,
) -> dict[str, float]:
    """Run a single query and return timing metrics."""
    t_start = time.perf_counter()

    # Embed the question
    embeddings = await embed_texts([question])
    query_embedding = embeddings[0]

    # Retrieve chunks
    chunks = query_chunks(repo_id, query_embedding, top_k=8)

    # Stream response, measure time to first token
    ttft: float | None = None
    async for _token in stream_response(question, chunks):
        if ttft is None:
            ttft = time.perf_counter() - t_start

    t_total = time.perf_counter() - t_start
    return {"ttft": ttft or t_total, "total": t_total}


async def main() -> None:
    print("=" * 60)
    print("  RepoPilot Benchmark")
    print("=" * 60)
    print(f"\nTarget repo: {REPO_URL}\n")

    # --- Indexing ---
    print("Indexing...", flush=True)
    repo_id, repo_path, files, chunks, idx_timings = await bench_indexing()

    print(f"\n--- Indexing Results ---")
    print(f"  Files processed   : {files}")
    print(f"  Chunks created    : {chunks}")
    print(f"  Clone time        : {idx_timings['clone']:.2f}s")
    print(f"  Chunk time        : {idx_timings['chunk']:.2f}s")
    print(f"  Embed time        : {idx_timings['embed']:.2f}s")
    print(f"  Store time        : {idx_timings['store']:.2f}s")
    print(f"  Total index time  : {idx_timings['total']:.2f}s")

    # --- Queries ---
    print(f"\n--- Query Results ---")
    ttfts: list[float] = []
    totals: list[float] = []

    for i, question in enumerate(QUESTIONS, 1):
        print(f"\n  Q{i}: {question}")
        metrics = await bench_query(repo_id, question)
        ttfts.append(metrics["ttft"])
        totals.append(metrics["total"])
        print(f"      Time to first token : {metrics['ttft']:.2f}s")
        print(f"      Total response time : {metrics['total']:.2f}s")

    # --- Summary ---
    num_languages = len({
        ext.lstrip(".")
        for ext in ALLOWED_EXTENSIONS
    })

    print(f"\n{'=' * 60}")
    print(f"  Summary")
    print(f"{'=' * 60}")
    print(f"  Files processed        : {files}")
    print(f"  Chunks created         : {chunks}")
    print(f"  Total indexing time    : {idx_timings['total']:.2f}s")
    print(f"  Avg time to first token: {sum(ttfts) / len(ttfts):.2f}s")
    print(f"  Avg total response time: {sum(totals) / len(totals):.2f}s")
    print(f"  Supported extensions   : {num_languages}")
    print()

    # Cleanup
    cleanup_repo(repo_path)
    try:
        delete_repo(repo_id)
    except Exception:
        pass


if __name__ == "__main__":
    asyncio.run(main())
