"""Service for parsing and chunking code files.

This is the core of the RAG pipeline. It walks a repository, filters to
code files, and splits them into semantically meaningful chunks that
preserve function/class boundaries where possible.
"""

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# File filtering config
# ---------------------------------------------------------------------------

SKIP_DIRS = {
    "node_modules", ".git", "__pycache__", "venv", ".venv", "env",
    ".env", ".tox", ".mypy_cache", ".pytest_cache", "dist", "build",
    ".next", ".nuxt", "coverage", ".idea", ".vscode",
}

SKIP_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "pnpm-lock.yaml",
    "Pipfile.lock", "composer.lock", "Gemfile.lock", "Cargo.lock",
}

ALLOWED_EXTENSIONS = {
    ".py", ".js", ".ts", ".tsx", ".jsx",
    ".java", ".go", ".rs", ".cpp", ".c", ".h",
    ".css", ".html", ".md",
    ".json", ".yaml", ".yml",
    ".sql", ".sh",
}

# Map file extension → language name
EXTENSION_TO_LANGUAGE = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".go": "go",
    ".rs": "rust",
    ".cpp": "cpp", ".c": "c", ".h": "c",
    ".css": "css", ".html": "html", ".md": "markdown",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml",
    ".sql": "sql", ".sh": "shell",
}

# ---------------------------------------------------------------------------
# Regex patterns for top-level definitions by language
# ---------------------------------------------------------------------------

# Each pattern matches the *start* of a top-level definition line.
# We anchor on zero indentation (^) so we only split at top-level scope.
SPLIT_PATTERNS: dict[str, re.Pattern] = {
    "python": re.compile(
        r"^(?:def |class |async def )", re.MULTILINE,
    ),
    "javascript": re.compile(
        r"^(?:"
        r"function\s|"                        # function foo(
        r"(?:export\s+)?(?:default\s+)?function\s|"
        r"(?:const|let|var)\s+\w+\s*=\s*(?:\(|async)|"  # const foo = ( / async
        r"(?:export\s+)?class\s"
        r")", re.MULTILINE,
    ),
    "typescript": re.compile(
        r"^(?:"
        r"function\s|"
        r"(?:export\s+)?(?:default\s+)?function\s|"
        r"(?:const|let|var)\s+\w+\s*=\s*(?:\(|async)|"
        r"(?:export\s+)?(?:class|interface|type|enum)\s"
        r")", re.MULTILINE,
    ),
    "java": re.compile(
        r"^(?:"
        r"(?:public|private|protected|static|\s)*\s+class\s|"
        r"(?:public|private|protected|static|\s)*\s+\w+\s+\w+\s*\("  # methods
        r")", re.MULTILINE,
    ),
    "go": re.compile(
        r"^(?:func |type )", re.MULTILINE,
    ),
    "rust": re.compile(
        r"^(?:pub\s+)?(?:fn |struct |enum |impl |trait |mod )", re.MULTILINE,
    ),
    "cpp": re.compile(
        r"^(?:"
        r"(?:class|struct|namespace)\s|"
        r"\w[\w\s\*&:<>]*\s+\w+\s*\("  # function definitions
        r")", re.MULTILINE,
    ),
    "c": re.compile(
        r"^(?:"
        r"(?:struct|typedef)\s|"
        r"\w[\w\s\*]*\s+\w+\s*\("
        r")", re.MULTILINE,
    ),
}

# Threshold: files under this many lines become a single chunk
SMALL_FILE_THRESHOLD = 80

# Fallback chunking parameters
FALLBACK_CHUNK_LINES = 60
FALLBACK_OVERLAP_LINES = 10

# Safety net: max characters per chunk (~1500 tokens for embedding model)
MAX_CHUNK_CHARS = 6000


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def chunk_repository(repo_path: str, repo_id: str) -> list[dict]:
    """Walk a repository and split every code file into chunks.

    Args:
        repo_path: Absolute path to the cloned repository on disk.
        repo_id: UUID string identifying this repository.

    Returns:
        List of chunk dicts, each containing:
            content, filename, start_line, end_line, language, chunk_id
    """
    repo_root = Path(repo_path)
    chunks: list[dict] = []

    for file_path in _iter_code_files(repo_root):
        rel_path = str(file_path.relative_to(repo_root))
        language = EXTENSION_TO_LANGUAGE.get(file_path.suffix, "plaintext")

        try:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue

        lines = text.splitlines(keepends=True)
        if not lines:
            continue

        file_chunks = _chunk_file(lines, language)

        # Safety net: re-split any chunk that exceeds MAX_CHUNK_CHARS
        file_chunks = _enforce_max_size(lines, file_chunks)

        for start, end, content in file_chunks:
            chunk_id = f"{repo_id}:{rel_path}:{start}"
            chunks.append({
                "content": content,
                "filename": rel_path,
                "start_line": start,
                "end_line": end,
                "language": language,
                "chunk_id": chunk_id,
            })

    return chunks


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _iter_code_files(root: Path):
    """Yield Path objects for every code file we should process."""
    for dirpath, dirnames, filenames in os.walk(root):
        # Prune skipped directories in-place so os.walk doesn't descend
        dirnames[:] = [
            d for d in dirnames if d not in SKIP_DIRS
        ]

        for fname in filenames:
            if fname in SKIP_FILES:
                continue
            if fname.endswith(".min.js") or fname.endswith(".min.css"):
                continue

            fpath = Path(dirpath) / fname
            if fpath.suffix in ALLOWED_EXTENSIONS:
                yield fpath


def _chunk_file(
    lines: list[str], language: str,
) -> list[tuple[int, int, str]]:
    """Split a file's lines into chunks.

    Returns a list of (start_line, end_line, content) tuples.
    Line numbers are 1-indexed.
    """
    if len(lines) < SMALL_FILE_THRESHOLD:
        return [(1, len(lines), "".join(lines))]

    # Try regex-based splitting first
    pattern = SPLIT_PATTERNS.get(language)
    if pattern is not None:
        chunks = _split_by_definitions(lines, pattern)
        if len(chunks) > 1:
            return chunks

    # Fallback: fixed-size windows with overlap
    return _split_by_lines(lines, FALLBACK_CHUNK_LINES, FALLBACK_OVERLAP_LINES)


def _split_by_definitions(
    lines: list[str], pattern: re.Pattern,
) -> list[tuple[int, int, str]]:
    """Split on top-level definitions found by *pattern*.

    Each definition and its body (up to the next definition) becomes one
    chunk. Any preamble (imports, module docstring) before the first
    definition becomes its own chunk.
    """
    # Find 0-indexed line numbers where definitions start
    split_indices: list[int] = []
    for i, line in enumerate(lines):
        if pattern.match(line):
            split_indices.append(i)

    if not split_indices:
        return []

    chunks: list[tuple[int, int, str]] = []

    # Preamble: everything before the first definition
    if split_indices[0] > 0:
        preamble = lines[: split_indices[0]]
        # Only keep preamble if it has non-blank content
        if any(l.strip() for l in preamble):
            chunks.append((
                1,
                split_indices[0],
                "".join(preamble),
            ))

    # Each definition → next definition (or EOF)
    for idx, start in enumerate(split_indices):
        end = split_indices[idx + 1] if idx + 1 < len(split_indices) else len(lines)
        chunk_lines = lines[start:end]
        chunks.append((
            start + 1,   # 1-indexed
            end,
            "".join(chunk_lines),
        ))

    return chunks


def _split_by_lines(
    lines: list[str], chunk_size: int, overlap: int,
) -> list[tuple[int, int, str]]:
    """Fall back to fixed-size windows with overlap."""
    chunks: list[tuple[int, int, str]] = []
    total = len(lines)
    start = 0

    while start < total:
        end = min(start + chunk_size, total)
        chunk_lines = lines[start:end]
        chunks.append((
            start + 1,   # 1-indexed
            end,
            "".join(chunk_lines),
        ))
        # Advance by (chunk_size - overlap), but always make progress
        start += max(chunk_size - overlap, 1)

    return chunks


def _enforce_max_size(
    all_lines: list[str],
    chunks: list[tuple[int, int, str]],
) -> list[tuple[int, int, str]]:
    """Re-split any chunk whose content exceeds MAX_CHUNK_CHARS.

    This is a safety net that catches oversized functions/classes the
    regex splitter kept as a single chunk.
    """
    result: list[tuple[int, int, str]] = []

    for start, end, content in chunks:
        if len(content) <= MAX_CHUNK_CHARS:
            result.append((start, end, content))
            continue

        # Re-split this oversized chunk using line-based windowing.
        # start/end are 1-indexed; all_lines is 0-indexed.
        chunk_lines = all_lines[start - 1 : end]
        sub_chunks = _split_by_lines(
            chunk_lines, FALLBACK_CHUNK_LINES, FALLBACK_OVERLAP_LINES,
        )
        # Adjust line numbers back to file-level offsets
        for sub_start, sub_end, sub_content in sub_chunks:
            result.append((
                start + sub_start - 1,  # re-anchor to file
                start + sub_end - 1,
                sub_content,
            ))

    return result
