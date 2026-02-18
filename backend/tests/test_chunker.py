"""Tests for the chunker service."""

from app.services.chunker import (
    chunk_repository,
    SMALL_FILE_THRESHOLD,
    FALLBACK_CHUNK_LINES,
    FALLBACK_OVERLAP_LINES,
    MAX_CHUNK_CHARS,
)


def test_small_file_is_single_chunk(fake_repo):
    """Files under SMALL_FILE_THRESHOLD lines should produce exactly one chunk."""
    chunks = chunk_repository(fake_repo, "test-repo")
    utils_chunks = [c for c in chunks if c["filename"] == "src/utils.py"]

    assert len(utils_chunks) == 1
    assert "def hello" in utils_chunks[0]["content"]
    assert utils_chunks[0]["start_line"] == 1


def test_large_file_produces_multiple_chunks(fake_repo):
    """Files over SMALL_FILE_THRESHOLD lines should be split into >1 chunk."""
    chunks = chunk_repository(fake_repo, "test-repo")
    engine_chunks = [c for c in chunks if c["filename"] == "src/engine.py"]

    assert len(engine_chunks) > 1


def test_python_regex_splitting(fake_repo):
    """Large Python files should split on 'def' boundaries."""
    chunks = chunk_repository(fake_repo, "test-repo")
    engine_chunks = [c for c in chunks if c["filename"] == "src/engine.py"]

    # engine.py has 4 top-level defs + a preamble → expect 5 chunks
    # (preamble with 'import sys', then func_0 through func_3)
    assert len(engine_chunks) >= 4

    # First chunk after preamble should start with def func_0
    func_chunks = [c for c in engine_chunks if "def func_" in c["content"]]
    assert len(func_chunks) == 4


def test_javascript_regex_splitting(fake_repo):
    """Large JS files should split on 'function' boundaries."""
    chunks = chunk_repository(fake_repo, "test-repo")
    app_chunks = [c for c in chunks if c["filename"] == "lib/app.js"]

    assert len(app_chunks) > 1

    func_chunks = [c for c in app_chunks if "function handler_" in c["content"]]
    assert len(func_chunks) == 3


def test_node_modules_skipped(fake_repo):
    """Files inside node_modules should not be chunked."""
    chunks = chunk_repository(fake_repo, "test-repo")
    nm_chunks = [c for c in chunks if "node_modules" in c["filename"]]

    assert len(nm_chunks) == 0


def test_lock_files_skipped(fake_repo):
    """Lock files (package-lock.json, etc.) should be skipped."""
    chunks = chunk_repository(fake_repo, "test-repo")
    lock_chunks = [c for c in chunks if "package-lock" in c["filename"]]

    assert len(lock_chunks) == 0


def test_non_code_files_skipped(fake_repo):
    """Files with disallowed extensions (.png, etc.) should be skipped."""
    chunks = chunk_repository(fake_repo, "test-repo")
    png_chunks = [c for c in chunks if c["filename"].endswith(".png")]

    assert len(png_chunks) == 0


def test_chunk_metadata_correct(fake_repo):
    """Each chunk should have all required metadata fields with correct types."""
    chunks = chunk_repository(fake_repo, "test-repo")

    for chunk in chunks:
        assert "content" in chunk and isinstance(chunk["content"], str)
        assert "filename" in chunk and isinstance(chunk["filename"], str)
        assert "start_line" in chunk and isinstance(chunk["start_line"], int)
        assert "end_line" in chunk and isinstance(chunk["end_line"], int)
        assert "language" in chunk and isinstance(chunk["language"], str)
        assert "chunk_id" in chunk and isinstance(chunk["chunk_id"], str)

        assert chunk["start_line"] >= 1
        assert chunk["end_line"] >= chunk["start_line"]
        assert chunk["chunk_id"].startswith("test-repo:")


def test_language_detection(fake_repo):
    """Language should be correctly detected from file extension."""
    chunks = chunk_repository(fake_repo, "test-repo")

    py_chunks = [c for c in chunks if c["filename"].endswith(".py")]
    js_chunks = [c for c in chunks if c["filename"].endswith(".js")]

    assert all(c["language"] == "python" for c in py_chunks)
    assert all(c["language"] == "javascript" for c in js_chunks)


def test_fallback_overlap(tmp_path):
    """When fallback line splitting is used, chunks should overlap by FALLBACK_OVERLAP_LINES."""
    # Create a file with 150 lines of plain text (no function defs → triggers fallback)
    repo = tmp_path / "overlap-repo"
    repo.mkdir()
    lines = [f"line {i}\n" for i in range(150)]
    (repo / "data.md").write_text("".join(lines))

    chunks = chunk_repository(str(repo), "overlap-test")

    assert len(chunks) >= 2

    # Check overlap: chunk[1].start_line should be chunk[0].end_line - overlap + 1
    c0, c1 = chunks[0], chunks[1]
    overlap = c0["end_line"] - c1["start_line"] + 1
    assert overlap == FALLBACK_OVERLAP_LINES


def test_no_chunk_exceeds_max_chars(tmp_path):
    """The safety net should prevent any chunk from exceeding MAX_CHUNK_CHARS."""
    repo = tmp_path / "big-repo"
    repo.mkdir()
    # Create a Python file with one huge function (200 lines × 50 chars)
    lines = ["def mega_function():\n"]
    for i in range(200):
        lines.append(f"    x_{i} = " + "a" * 40 + "\n")
    (repo / "big.py").write_text("".join(lines))

    chunks = chunk_repository(str(repo), "big-test")

    for chunk in chunks:
        assert len(chunk["content"]) <= MAX_CHUNK_CHARS, (
            f"Chunk {chunk['chunk_id']} exceeds MAX_CHUNK_CHARS: "
            f"{len(chunk['content'])} > {MAX_CHUNK_CHARS}"
        )
