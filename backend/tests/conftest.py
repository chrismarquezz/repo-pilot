"""Shared test fixtures."""

import os

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


# ---------------------------------------------------------------------------
# FastAPI test client
# ---------------------------------------------------------------------------

@pytest.fixture
async def client():
    """Async HTTP client for testing FastAPI endpoints."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ---------------------------------------------------------------------------
# Fake repository on disk
# ---------------------------------------------------------------------------

SMALL_PY = """\
import os

def hello():
    return "hello"

def goodbye():
    return "goodbye"
"""

SMALL_JS = """\
function greet(name) {
    return `Hello, ${name}`;
}

module.exports = { greet };
"""


def _make_large_py() -> str:
    """Generate a Python file with 4 top-level functions, well over 80 lines."""
    lines = ["import sys\n", "\n"]
    for i in range(4):
        lines.append(f"def func_{i}(x):\n")
        for j in range(30):
            lines.append(f"    line_{j} = {j}\n")
        lines.append("\n")
    return "".join(lines)


def _make_large_js() -> str:
    """Generate a JS file with 3 functions, well over 80 lines."""
    lines = ["// App module\n", "\n"]
    for i in range(3):
        lines.append(f"function handler_{i}(req, res) {{\n")
        for j in range(32):
            lines.append(f"    const v{j} = {j};\n")
        lines.append("}\n")
        lines.append("\n")
    return "".join(lines)


@pytest.fixture
def fake_repo(tmp_path):
    """Create a temporary directory that looks like a small code repository.

    Structure:
        src/
            utils.py       (small — ~7 lines)
            engine.py      (large — ~126 lines with multiple defs)
        lib/
            helpers.js     (small — ~5 lines)
            app.js         (large — ~104 lines with functions)
        node_modules/
            pkg/index.js   (should be skipped)
        package-lock.json  (should be skipped)
        logo.png           (should be skipped — not in allowed extensions)
    """
    repo = tmp_path / "fake-repo"
    repo.mkdir()

    # src/utils.py — small file
    src = repo / "src"
    src.mkdir()
    (src / "utils.py").write_text(SMALL_PY)

    # src/engine.py — large Python file
    engine_text = _make_large_py()
    assert engine_text.count("\n") > 80
    (src / "engine.py").write_text(engine_text)

    # lib/helpers.js — small file
    lib = repo / "lib"
    lib.mkdir()
    (lib / "helpers.js").write_text(SMALL_JS)

    # lib/app.js — large JS file
    app_text = _make_large_js()
    assert app_text.count("\n") > 80
    (lib / "app.js").write_text(app_text)

    # node_modules — should be skipped entirely
    nm = repo / "node_modules" / "pkg"
    nm.mkdir(parents=True)
    (nm / "index.js").write_text("module.exports = {};")

    # Lock file — should be skipped
    (repo / "package-lock.json").write_text("{}")

    # Binary/image — not in allowed extensions, should be skipped
    (repo / "logo.png").write_bytes(b"\x89PNG fake")

    return str(repo)
