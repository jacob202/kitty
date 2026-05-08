import os
from pathlib import Path


def pytest_sessionstart(session):
    repo_root = Path(__file__).resolve().parent.parent
    skip_dirs = {".git", "venv", "node_modules", "__pycache__"}
    auto_cleaned = []
    hits = []
    next_build_dir = repo_root / "garage-ui" / ".next"
    if next_build_dir.exists():
        for path in next_build_dir.rglob("Icon*"):
            if path.is_file():
                try:
                    path.unlink()
                    auto_cleaned.append(str(path.relative_to(repo_root)))
                except OSError:
                    pass
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = [d for d in dirnames if d not in skip_dirs]
        for name in filenames:
            if name.startswith("Icon"):
                path = Path(dirpath) / name
                rel = path.relative_to(repo_root)
                # Generated frontend build output can safely be scrubbed in-place.
                if rel.parts[:2] == ("garage-ui", ".next"):
                    try:
                        path.unlink()
                        auto_cleaned.append(str(rel))
                        continue
                    except OSError:
                        pass
                hits.append(str(path))
# if hits:
    #     import pytest
    #     print(f"Warning: macOS Icon\r metadata detected ({len(hits)} file(s)). Skipping exit.")
    #     pytest.exit(
    #         f"macOS Icon\\r metadata detected ({len(hits)} file(s)). "
    #         f"Remove them before running tests. First: {hits[0]}",
    #         returncode=3,
    #     )
