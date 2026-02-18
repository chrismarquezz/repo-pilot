"""Tests for the /api/query endpoint."""


async def test_query_missing_repo(client):
    """POST /api/query with non-existent repo_id should return 404."""
    res = await client.post(
        "/api/query",
        json={"repo_id": "nonexistent-repo-xyz", "question": "What does this do?"},
    )
    assert res.status_code == 404


async def test_query_missing_fields(client):
    """POST /api/query with missing fields should return 422."""
    res = await client.post("/api/query", json={})
    assert res.status_code == 422

    res = await client.post("/api/query", json={"repo_id": "some-repo"})
    assert res.status_code == 422

    res = await client.post("/api/query", json={"question": "hello?"})
    assert res.status_code == 422


async def test_query_returns_sse_stream(client, monkeypatch):
    """POST /api/query should return text/event-stream content type."""
    # Mock embed_texts
    async def mock_embed(texts):
        return [[0.1] * 1536 for _ in texts]

    # Mock query_chunks to return fake results
    def mock_query(repo_id, embedding, top_k=8):
        return [
            {
                "content": "def hello(): pass",
                "filename": "main.py",
                "start_line": 1,
                "end_line": 1,
                "language": "python",
                "score": 0.95,
            }
        ]

    # Mock stream_response to yield a few tokens
    async def mock_stream(question, chunks):
        yield "Hello "
        yield "world"

    monkeypatch.setattr("app.routers.query.embed_texts", mock_embed)
    monkeypatch.setattr("app.routers.query.query_chunks", mock_query)
    monkeypatch.setattr("app.routers.query.stream_response", mock_stream)

    res = await client.post(
        "/api/query",
        json={"repo_id": "test-repo", "question": "What does hello do?"},
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    # Parse the SSE body
    body = res.text
    lines = [l for l in body.strip().split("\n") if l.startswith("data: ")]

    assert len(lines) >= 3  # sources + at least 1 token + done

    import json

    # First event should be sources
    first = json.loads(lines[0].removeprefix("data: "))
    assert first["type"] == "sources"
    assert len(first["chunks"]) == 1
    assert first["chunks"][0]["filename"] == "main.py"

    # Last event should be done
    last = json.loads(lines[-1].removeprefix("data: "))
    assert last["type"] == "done"

    # Middle events should be tokens
    tokens = [
        json.loads(l.removeprefix("data: "))
        for l in lines[1:-1]
    ]
    assert all(t["type"] == "token" for t in tokens)
    full_text = "".join(t["content"] for t in tokens)
    assert full_text == "Hello world"
