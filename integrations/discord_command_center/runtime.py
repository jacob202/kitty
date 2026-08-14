from __future__ import annotations

import shutil
from collections.abc import Mapping
from pathlib import Path


class CodexRuntime:
    """Disposable Codex state kept inside the run worktree."""

    dirname = ".command-center-runtime"

    def __init__(self, worktree: Path, source_environment: Mapping[str, str]) -> None:
        self.path = worktree / self.dirname
        self.source_environment = source_environment

    def prepare(self) -> Path:
        if self.path.exists() or self.path.is_symlink():
            raise FileExistsError(f"Codex runtime already exists: {self.path}")
        self.path.mkdir(mode=0o700)
        auth_source = self._auth_source()
        if not auth_source.is_file():
            self.cleanup()
            raise RuntimeError(f"Codex auth file not found: {auth_source}")
        (self.path / "auth.json").symlink_to(auth_source)
        return self.path

    @property
    def auth_source(self) -> Path:
        return self._auth_source().resolve()

    def cleanup(self) -> None:
        if self.path.exists() or self.path.is_symlink():
            shutil.rmtree(self.path)

    def _auth_source(self) -> Path:
        codex_home = self.source_environment.get("CODEX_HOME")
        if codex_home:
            return Path(codex_home).expanduser() / "auth.json"
        home = Path(self.source_environment.get("HOME", str(Path.home()))).expanduser()
        return home / ".codex" / "auth.json"
