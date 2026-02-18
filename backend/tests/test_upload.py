"""Tests for the /api/upload endpoint."""


async def test_upload_invalid_url(client):
    """POST /api/upload with invalid GitHub URL should return 422."""
    res = await client.post("/api/upload", json={"github_url": "not-a-url"})
    assert res.status_code == 422
    assert "Invalid GitHub URL" in res.json()["detail"]


async def test_upload_missing_body(client):
    """POST /api/upload with empty body should return 422 (Pydantic validation)."""
    res = await client.post("/api/upload", json={})
    assert res.status_code == 422


async def test_upload_missing_field(client):
    """POST /api/upload with wrong field name should return 422."""
    res = await client.post("/api/upload", json={"url": "https://github.com/user/repo"})
    assert res.status_code == 422


async def test_upload_response_schema(client, monkeypatch):
    """POST /api/upload with valid input should return the correct response shape."""
    # Mock clone_repo to return a temp dir with a small file
    import tempfile, os
    tmp = tempfile.mkdtemp(prefix="repopilot_")
    repo_dir = os.path.join(tmp, "test-repo")
    os.makedirs(repo_dir)
    with open(os.path.join(repo_dir, "main.py"), "w") as f:
        f.write("def hello():\n    return 'hi'\n")

    async def mock_clone(url):
        return repo_dir

    def mock_cleanup(path):
        pass

    # Mock embed_texts to return fake embeddings
    async def mock_embed(texts):
        return [[0.1] * 1536 for _ in texts]

    monkeypatch.setattr("app.routers.upload.clone_repo", mock_clone)
    monkeypatch.setattr("app.routers.upload.cleanup_repo", mock_cleanup)
    monkeypatch.setattr("app.routers.upload.embed_texts", mock_embed)

    res = await client.post(
        "/api/upload", json={"github_url": "https://github.com/user/test-repo"}
    )
    assert res.status_code == 200

    data = res.json()
    assert data["status"] == "indexed"
    assert data["repo_name"] == "test-repo"
    assert data["files_processed"] >= 1
    assert data["chunks_created"] >= 1
    assert "repo_id" in data

    # Clean up the ChromaDB collection
    from app.services.vectorstore import delete_repo
    delete_repo(data["repo_id"])

    import shutil
    shutil.rmtree(tmp, ignore_errors=True)
