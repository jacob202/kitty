import os
from pathlib import Path


def pytest_sessionstart(session):
    repo_root = Path(__file__).resolve().parent.parent
    skip_dirs = {".git", "venv", "node_modules", "__pycache__"}
    hits = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            if name == "Icon\r" or name == "Icon%0D":
                hits.append(os.path.join(dirpath, name))
    if hits:
        import pytest
        pytest.exit(
            f"macOS Icon\\r metadata detected ({len(hits)} file(s)). "
            f"Remove them before running tests. First: {hits[0]}",
            returncode=3,
        )
