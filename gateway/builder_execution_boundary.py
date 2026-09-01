"""Lower-trust process boundary for KittyBuilder model subprocesses.

The supported macOS runtime uses Seatbelt to keep model-controlled worker and
reviewer process trees inside their worktree/run-artifact boundary while still
allowing outbound provider traffic. Loopback network access is denied so a
child cannot acquire Gateway authority through Kitty's authenticated UI proxy.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path

_SAFE_INHERITED_ENV = {
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TERM",
    "COLORTERM",
    "TZ",
}
_SAFE_PATH = "/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"


def build_child_environment(
    source: Mapping[str, str] | None = None,
    *,
    run_dir: Path,
) -> dict[str, str]:
    """Return a secret-free base environment rooted in Builder artifacts."""
    source = os.environ if source is None else source
    run_dir = run_dir.resolve()
    home = run_dir / "child-home"
    tmp = run_dir / "tmp"
    for path in (run_dir, home, tmp):
        path.mkdir(parents=True, exist_ok=True, mode=0o700)

    child = {
        key: value
        for key, value in source.items()
        if key in _SAFE_INHERITED_ENV and value
    }
    child.update(
        PATH=_SAFE_PATH,
        HOME=str(home),
        TMPDIR=str(tmp),
        TMP=str(tmp),
        TEMP=str(tmp),
        XDG_CONFIG_HOME=str(home / ".config"),
        XDG_DATA_HOME=str(home / ".local" / "share"),
        XDG_CACHE_HOME=str(home / ".cache"),
    )
    command_line_tools = Path("/Library/Developer/CommandLineTools")
    if sys.platform == "darwin" and command_line_tools.is_dir():
        # Apple's /usr/bin tool shims refuse to run when xcode-select points at
        # a full Xcode whose licence has not been accepted, which kills a child
        # before it can report anything. The Command Line Tools have no licence
        # prompt, so pin children to them.
        child["DEVELOPER_DIR"] = str(command_line_tools)
    return child


def containment_mode() -> str:
    if sys.platform == "darwin" and Path("/usr/bin/sandbox-exec").is_file():
        return "macos-seatbelt"
    return "env-only-unsupported-platform"


def wrap_command(
    command: Sequence[str],
    *,
    worktree: Path,
    run_dir: Path,
    environment: Mapping[str, str],
    read_paths: Sequence[Path] = (),
    extra_read_subpaths: Sequence[Path] = (),
    write_paths: Sequence[Path] = (),
    worktree_writable: bool = True,
) -> list[str]:
    """Wrap a child command in the supported host sandbox when available."""
    if not command:
        raise ValueError("command must not be empty")
    if containment_mode() != "macos-seatbelt":
        return list(command)
    profile = build_sandbox_profile(
        worktree=worktree,
        run_dir=run_dir,
        command=command,
        environment=environment,
        read_paths=read_paths,
        extra_read_subpaths=extra_read_subpaths,
        write_paths=write_paths,
        worktree_writable=worktree_writable,
    )
    return ["/usr/bin/sandbox-exec", "-p", profile, *command]


def build_sandbox_profile(
    *,
    worktree: Path,
    run_dir: Path,
    command: Sequence[str],
    environment: Mapping[str, str],
    read_paths: Sequence[Path] = (),
    extra_read_subpaths: Sequence[Path] = (),
    write_paths: Sequence[Path] = (),
    worktree_writable: bool = True,
) -> str:
    """Build a macOS Seatbelt profile for one Builder child process tree."""
    worktree = worktree.resolve()
    run_dir = run_dir.resolve()
    executable = _resolve_executable(command[0], worktree, environment)
    launch_executable = Path(os.path.abspath(executable))

    read_subpaths = {
        str(worktree),
        str(run_dir),
        "/bin",
        "/sbin",
        "/usr/bin",
        "/usr/sbin",
        "/usr/lib",
        "/usr/libexec",
        "/usr/share",
        "/System/Library",
        "/Library/Preferences",
        "/private/etc",
        "/private/var/db/timezone",
        "/opt/homebrew",
        "/usr/local",
    }
    # A venv/interpreter may live outside the task worktree. It is executable
    # support, not mutable Builder state, so expose that installation read-only.
    resolved_executable = executable.resolve()
    if "bin" in resolved_executable.parts:
        bin_index = len(resolved_executable.parts) - 1 - resolved_executable.parts[::-1].index("bin")
        if bin_index > 0:
            read_subpaths.add(str(Path(*resolved_executable.parts[:bin_index]).resolve()))

    read_subpaths.update(_command_support_read_paths(command, worktree))
    # Both spellings: Seatbelt matches an alias directory by the name the
    # caller uses, so resolving these away would deny a symlinked toolchain.
    for path in extra_read_subpaths:
        read_subpaths.add(str(Path(path).absolute()))
        read_subpaths.add(str(Path(path).resolve()))
    git_subpaths, git_literals = _git_metadata_read_paths(worktree)
    read_subpaths.update(git_subpaths)
    read_literals = {
        *(str(Path(path).resolve()) for path in read_paths),
        "/",
        "/dev/null",
        "/dev/urandom",
        "/dev/random",
        str(launch_executable),
        str(resolved_executable),
        *git_literals,
    }
    metadata_literals = {
        "/",
        "/Applications",
        "/Library",
        "/System",
        "/Users",
        "/dev",
        "/etc",
        "/opt",
        "/private",
        "/usr",
        "/var",
    }
    # Seatbelt requires directory metadata traversal to reach explicitly
    # readable paths; metadata access does not grant file content. Trusted
    # command-support directories may live outside the packet worktree.
    for read_path in read_subpaths:
        variant = Path(read_path).resolve()
        metadata_literals.add(str(variant))
        metadata_literals.update(str(parent) for parent in variant.parents)
    for path in (launch_executable, resolved_executable, worktree, run_dir, *extra_read_subpaths):
        for variant in (Path(path).absolute(), Path(path).resolve()):
            metadata_literals.add(str(variant))
            metadata_literals.update(str(parent) for parent in variant.parents)
    # Git resolves a linked worktree through the common .git/worktrees tree.
    # The content under those directories is already narrowly read-enabled
    # above; allow metadata traversal of their parent directories so Git can
    # resolve the explicitly permitted paths under Seatbelt.
    for git_path in [*(Path(path) for path in git_subpaths), *(Path(path) for path in git_literals)]:
        metadata_literals.update(str(parent) for parent in git_path.parents)

    read_rules = " ".join(
        [
            *(f'(allow file-read* (subpath "{_escape(path)}"))' for path in sorted(read_subpaths)),
            *(f'(allow file-read* (literal "{_escape(path)}"))' for path in sorted(read_literals)),
            *(f'(allow file-read-metadata (literal "{_escape(path)}"))' for path in sorted(metadata_literals)),
        ]
    )
    writable_subpaths = {str(run_dir)}
    if worktree_writable:
        writable_subpaths.add(str(worktree))
    write_rules = " ".join(
        [
            *(f'(allow file-write* (subpath "{_escape(path)}"))' for path in sorted(writable_subpaths)),
            *(f'(allow file-write* (literal "{_escape(str(Path(path).resolve()))}"))' for path in write_paths),
        ]
    )
    return (
        '(version 1) '
        '(allow process*) (allow signal (target same-sandbox)) '
        '(allow sysctl-read) (allow mach-lookup) '
        '(deny file-read*) '
        f'{read_rules} '
        '(deny file-write*) '
        f'{write_rules} '
        '(allow file-write* (literal "/dev/null")) '
        '(allow network-outbound) '
        '(deny network-outbound (remote ip "localhost:*")) '
        '(allow system-info (info-type "net.link.addr")) '
        '(allow system-socket (require-all (socket-domain AF_SYSTEM) (socket-protocol 2))) '
        '(allow user-preference-read)'
    )


def _resolve_executable(
    value: str,
    worktree: Path,
    environment: Mapping[str, str],
) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        if not candidate.exists():
            raise FileNotFoundError(2, "No such file or directory", str(candidate))
        return candidate
    if "/" in value:
        return (worktree / candidate).resolve()
    resolved = shutil.which(value, path=environment.get("PATH"))
    if not resolved:
        raise FileNotFoundError(f"Builder child executable not found: {value}")
    return Path(resolved)


def _command_support_read_paths(command: Sequence[str], worktree: Path) -> set[str]:
    """Allow trusted command-support directories read-only.

    Builder chooses the command before the model runs. Shell/Python adapters
    commonly live outside the task worktree and load sibling helper files.
    Grant only directories containing explicit existing file arguments.
    """
    paths: set[str] = set()
    for raw in command[1:]:
        candidate = Path(raw)
        if not candidate.is_absolute() or not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved.is_relative_to(worktree):
            continue
        paths.add(str(resolved.parent))
    return paths


def boundary_git_executable() -> str:
    """Return the git Builder resolves from its own fixed PATH.

    Resolution stays inside ``_SAFE_PATH`` so a model-controlled environment
    cannot substitute a different git. ``/usr/bin/git`` alone is not usable:
    on a Mac with Xcode selected it is a shim that refuses to run until the
    licence is accepted, which would abort every worker launch.
    """
    return shutil.which("git", path=_SAFE_PATH) or "/usr/bin/git"


def _git_metadata_read_paths(worktree: Path) -> tuple[set[str], set[str]]:
    git_file = worktree / ".git"
    if not git_file.exists() and not git_file.is_symlink():
        return set(), set()
    result = subprocess.run(
        [boundary_git_executable(), "-C", str(worktree), "rev-parse", "--git-dir", "--git-common-dir"],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"could not resolve Builder worktree Git metadata: {detail}")
    values = [
        (worktree / Path(line)).resolve() if not Path(line).is_absolute() else Path(line).resolve()
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    if len(values) != 2:
        raise RuntimeError("could not resolve worktree and common Git metadata")
    worktree_git_dir, common_git_dir = values
    subpaths = {
        str(worktree_git_dir),
        str(common_git_dir / "objects"),
        str(common_git_dir / "refs"),
        str(common_git_dir / "info"),
    }
    literals = {
        str(path)
        for path in (
            common_git_dir / "HEAD",
            common_git_dir / "config",
            common_git_dir / "packed-refs",
            common_git_dir / "description",
        )
        if path.exists()
    }
    return subpaths, literals


def _escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
