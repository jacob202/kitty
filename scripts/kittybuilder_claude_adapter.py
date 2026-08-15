#!/usr/bin/env python3
"""Strict Claude Code worker/reviewer adapter for KittyBuilder packet attempts.

This adapter is the fixed-model, no-fallback sibling of the free OpenCode
adapter scripts. It drives Claude Code (``claude -p``) for exactly two roles:

    worker   implements one packet attempt (Sonnet by default)
    review   reads the implementation as an independent, read-only reviewer
             (Opus by default)

Strictness contract:

- **Fixed models, no fallback.** The worker uses one Sonnet model and the
  reviewer one Opus model; a failed run is never retried against a different
  model. Defaults are overridable only through explicit env vars
  (``KITTYBUILDER_CLAUDE_WORKER_MODEL`` / ``KITTYBUILDER_CLAUDE_REVIEW_MODEL``).
- **Exit 75 with no output and no change** when the ``claude`` executable is
  unavailable or authentication fails. The adapter probes auth with a tiny
  no-op request before any real work; a missing binary or a failed probe exits
  75 without writing a result, without leaving staging files, and without
  touching the worktree. Exit 75 is the loop's established provider-exhaustion
  code (``builder_loop.PROVIDER_EXHAUSTED_EXIT_CODE``).
- **Strict contracts.** Worker results and review results are validated against
  the same bounded JSON contracts as the OpenCode adapters (bundle/context hash
  binding, ``contract_version`` 1, fixed status/verdict enums).
- **Reviewer immutability.** The reviewer fingerprints HEAD and worktree status
  before and after the model run; any mutation aborts with no review published.

The test-suite drives this adapter with a fake ``claude`` executable found on
``PATH`` (or pinned via ``KITTYBUILDER_CLAUDE_BIN``), so no live Claude
request ever happens in tests.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

EXIT_UNAVAILABLE = 75  # matches builder_loop.PROVIDER_EXHAUSTED_EXIT_CODE
EXIT_CONTRACT = 1

DEFAULT_WORKER_MODEL = "claude-sonnet-4-5"
DEFAULT_REVIEWER_MODEL = "claude-opus-4-6"
PROBE_PROMPT = "Reply with exactly: ok"

_WORKER_REQUIRED_ENV = (
    "KB_BUNDLE_PATH",
    "KB_RESULT_PATH",
    "KB_CONTEXT_MANIFEST_PATH",
    "KB_ATTEMPT_ID",
    "KB_TASK_ID",
)

_REVIEW_REQUIRED_ENV = (
    "KB_BUNDLE_PATH",
    "KB_IMPL_RESULT_PATH",
    "KB_REVIEW_RESULT_PATH",
    "KB_CONTEXT_MANIFEST_PATH",
    "KB_REVIEW_CONTEXT_PATH",
    "KB_REVIEW_SHA",
    "KB_REVIEW_DIFF_SHA256",
    "KB_ATTEMPT_ID",
    "KB_TASK_ID",
)


class AdapterError(RuntimeError):
    """Raised for contract violations; exits with EXIT_CONTRACT."""


def _fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return EXIT_CONTRACT


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise AdapterError(f"{name} is required")
    return value


def _git_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AdapterError("the adapter must run inside the task's isolated git worktree")
    return Path(result.stdout.strip())


def _resolve_claude_bin() -> Path | None:
    pinned = os.environ.get("KITTYBUILDER_CLAUDE_BIN")
    if pinned:
        candidate = Path(pinned)
        if candidate.is_file() and os.access(candidate, os.X_OK):
            return candidate
        return None
    found = shutil.which("claude")
    return Path(found) if found else None


def _stage(attempt_id: str, names: list[str]) -> dict[str, Path]:
    """Create staging paths in the worktree, refusing pre-existing ones.

    Mirrors the OpenCode adapters: the model must never see runner-owned paths
    directly, and a stale staging file is a hard error, not an overwrite.
    """
    staged: dict[str, Path] = {}
    for name in names:
        path = Path.cwd() / f".kittybuilder-claude-{name}-{attempt_id}.json"
        if path.exists():
            raise AdapterError(f"staging path already exists: {path}")
        staged[name] = path
    return staged


def _copy_staged(
    staged: dict[str, Path], mapping: dict[str, str]
) -> dict[str, Path]:
    for name, env_name in mapping.items():
        source = Path(_require_env(env_name))
        if not source.is_file():
            raise AdapterError(f"{env_name} does not point at a file: {source}")
        shutil.copyfile(source, staged[name])
    return staged


def _validate_worker_binding(
    bundle_path: Path, manifest_path: Path, task_id: str, attempt_id: str
) -> None:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("task_id") != task_id:
        raise AdapterError(
            f"context manifest task mismatch: {manifest.get('task_id')!r} != {task_id!r}"
        )
    if str(manifest.get("attempt_id")) != attempt_id:
        raise AdapterError(
            f"context manifest attempt mismatch: {manifest.get('attempt_id')!r} != {attempt_id!r}"
        )
    actual = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
    expected = manifest.get("bundle_sha256")
    nested = (manifest.get("context") or {}).get("task_bundle", {}).get("sha256")
    if actual != expected or actual != nested:
        raise AdapterError("context bundle hash does not match the run manifest")


def _validate_review_binding(
    bundle_path: Path,
    manifest_path: Path,
    review_context_path: Path,
    task_id: str,
    attempt_id: str,
    review_sha: str,
    diff_sha256: str,
) -> None:
    _validate_worker_binding(bundle_path, manifest_path, task_id, attempt_id)
    binding = json.loads(review_context_path.read_text(encoding="utf-8"))
    if binding.get("task_id") != task_id or str(binding.get("attempt_id")) != attempt_id:
        raise AdapterError("review context task/attempt identity mismatch")
    if binding.get("review_sha") != review_sha:
        raise AdapterError("review context SHA does not match KB_REVIEW_SHA")
    if binding.get("diff_sha256") != diff_sha256:
        raise AdapterError("review context diff does not match KB_REVIEW_DIFF_SHA256")


def _fingerprint() -> str:
    """HEAD plus worktree status, excluding reviewer continuation residue and staging files."""
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    status = subprocess.run(
        [
            "git", "status", "--porcelain=v1", "--untracked-files=all", "--",
            ".", ":(exclude).omo/run-continuation/**", ":(exclude).kittybuilder-claude-*.json",
        ],
        capture_output=True,
        text=True,
        check=False,
    ).stdout
    return f"{head}\n{status}"


def _probe_auth(bin_path: Path, model: str) -> tuple[str, str]:
    """Return (ok|unavailable|error, detail) for the no-op Claude probe."""
    timeout = float(os.environ.get("KITTYBUILDER_CLAUDE_PROBE_TIMEOUT", "30"))
    try:
        result = subprocess.run(
            [str(bin_path), "-p", "--model", model, PROBE_PROMPT],
            stdin=subprocess.DEVNULL, capture_output=True, text=True,
            timeout=timeout, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        return "error", f"claude probe timed out for model {model}: {exc}"
    except OSError as exc:
        return "error", f"claude probe could not run model {model}: {exc}"
    if result.returncode == 0:
        return "ok", ""
    detail = (result.stderr or result.stdout or "").strip()
    lowered = detail.lower()
    auth_markers = ("auth", "login", "unauthorized", "api key", "credential", "not authenticated")
    if not detail or any(marker in lowered for marker in auth_markers):
        return "unavailable", detail
    return "error", f"claude probe failed for model {model} (exit {result.returncode}): {detail}"


def _run_model(bin_path: Path, model: str, prompt: str, timeout: float) -> int:
    try:
        result = subprocess.run(
            [str(bin_path), "-p", "--model", model, prompt],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return 1
    return result.returncode


def _validate_worker_result(path: Path) -> dict:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("contract_version") != 1:
        raise AdapterError("worker result is not a contract_version=1 object")
    if result.get("status") not in {"completed", "failed"}:
        raise AdapterError("worker result has an invalid status")
    return result


def _validate_review_result(path: Path) -> dict:
    review = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(review, dict) or review.get("contract_version") != 1:
        raise AdapterError("reviewer result is not a contract_version=1 object")
    if review.get("verdict") not in {"approve", "request_changes", "reject"}:
        raise AdapterError("reviewer result has an invalid verdict")
    findings = review.get("findings")
    if findings is not None and not isinstance(findings, list):
        raise AdapterError("reviewer findings must be a list")
    return review


def _worker_prompt(staged: dict[str, Path]) -> str:
    bundle_sha = hashlib.sha256(staged["bundle"].read_bytes()).hexdigest()
    context_sha = hashlib.sha256(staged["context"].read_bytes()).hexdigest()
    result_path = staged["result"]
    return (
        "You are a KittyBuilder implementation worker in an isolated worktree.\n\n"
        "Read AGENTS.md, .claude/HANDOFF.md, and .claude/STATE.md before editing.\n"
        f"Read the packet context bundle at: {staged['bundle']}\n"
        f"Read the run/context manifest at: {staged['context']}\n"
        f"The local bundle SHA-256 is {bundle_sha}; the local manifest SHA-256 is {context_sha}.\n"
        "Do not read the runner-owned paths outside this worktree.\n\n"
        "Implement only the packet in that bundle. Stay within its allowed paths and\n"
        "acceptance criteria. Do not push, merge, delete files, touch secrets/env files,\n"
        "or inspect private runtime data. Run the declared validation commands and any\n"
        "focused tests that materially prove the change.\n\n"
        "Before you finish, write a JSON object to "
        f"{result_path} with exactly this shape (contract_version must be 1):\n"
        '{"contract_version":1,"status":"completed" or "failed","summary":"...","diff_summary":"...","validation":{"passed":true,"output":"..."},"claims":["..."]}\n\n'
        "Use status=failed if the implementation or validation cannot honestly pass.\n"
        "Then give a concise final report."
    )


def _reviewer_prompt(staged: dict[str, Path]) -> str:
    bundle_sha = hashlib.sha256(staged["bundle"].read_bytes()).hexdigest()
    impl_sha = hashlib.sha256(staged["impl"].read_bytes()).hexdigest()
    context_sha = hashlib.sha256(staged["context"].read_bytes()).hexdigest()
    binding_sha = hashlib.sha256(staged["binding"].read_bytes()).hexdigest()
    return (
        "You are an independent, read-only KittyBuilder reviewer in an isolated\n"
        "worktree. Do not edit files, commit, push, merge, or touch secrets.\n\n"
        f"Read AGENTS.md and the packet context bundle at: {staged['bundle']}\n"
        f"Read the implementation result at: {staged['impl']}\n"
        f"Read the run/context manifest at: {staged['context']}\n"
        f"Read the reviewer binding at: {staged['binding']}\n"
        f"Bundle SHA-256: {bundle_sha}\n"
        f"Implementation result SHA-256: {impl_sha}\n"
        f"Manifest SHA-256: {context_sha}\n"
        f"Reviewer binding SHA-256: {binding_sha}\n"
        f"Review HEAD (must remain unchanged): {os.environ['KB_REVIEW_SHA']}\n"
        f"Review diff SHA-256 (must remain unchanged): {os.environ['KB_REVIEW_DIFF_SHA256']}\n"
        "Inspect the current diff and run focused tests if useful.\n\n"
        f"Write a JSON object to {staged['review']} with exactly this shape\n"
        "(contract_version must be 1):\n"
        '{"contract_version":1,"verdict":"approve" or "request_changes" or "reject","summary":"...","findings":[{"severity":"critical" or "major" or "minor","note":"..."}]}\n\n'
        "Approve only if the acceptance criteria and validation evidence are honest."
    )


def _write_review_note(review: dict, note_path: Path, sha: str, model: str) -> None:
    lines = [
        "# KittyBuilder review note",
        "",
        f"- Reviewed commit: `{sha}`",
        f"- Verdict: {review.get('verdict')}",
        f"- Model: {model}",
        "",
        "## Summary",
        "",
        str(review.get("summary", "")),
    ]
    findings = review.get("findings")
    if isinstance(findings, list) and findings:
        lines += ["", "## Findings", ""]
        for item in findings:
            if isinstance(item, dict):
                lines.append(f"- [{item.get('severity', 'note')}] {item.get('note', '')}")
            else:
                lines.append(f"- {item}")
    lines.append("")
    note_path.write_text("\n".join(lines), encoding="utf-8")


def _commit_completed_work(task_id: str, attempt_id: str, packet_id: str) -> None:
    """Commit a real completed change on the model's behalf (adapter duty)."""
    status = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        capture_output=True, text=True, check=False,
    )
    if status.returncode != 0:
        raise AdapterError((status.stderr or status.stdout or "git status failed").strip())
    if not status.stdout.strip():
        return
    add = subprocess.run(["git", "add", "-A"], capture_output=True, text=True, check=False)
    if add.returncode != 0:
        raise AdapterError(f"git add failed: {(add.stderr or add.stdout).strip()}")
    commit = subprocess.run(
        ["git", "commit", "--quiet", "-m", f"[{packet_id}] kittybuilder: {task_id} attempt {attempt_id} (claude worker)"],
        capture_output=True, text=True, check=False,
    )
    if commit.returncode != 0:
        raise AdapterError(f"git commit failed: {(commit.stderr or commit.stdout).strip()}")



# ---------------------------------------------------------------------------
# Modes
# ---------------------------------------------------------------------------


def _run_worker() -> int:
    for name in _WORKER_REQUIRED_ENV:
        _require_env(name)
    task_id = _require_env("KB_TASK_ID")
    attempt_id = _require_env("KB_ATTEMPT_ID")
    try:
        _git_root()
    except AdapterError as exc:
        return _fail(str(exc))

    bin_path = _resolve_claude_bin()
    if bin_path is None:
        return EXIT_UNAVAILABLE

    staged = _stage(attempt_id, ["bundle", "context", "result"])
    try:
        try:
            _copy_staged(
                staged,
                {
                    "bundle": "KB_BUNDLE_PATH",
                    "context": "KB_CONTEXT_MANIFEST_PATH",
                },
            )
            _validate_worker_binding(
                staged["bundle"], staged["context"], task_id, attempt_id
            )
        except (AdapterError, json.JSONDecodeError, KeyError) as exc:
            return _fail(str(exc))

        model = os.environ.get(
            "KITTYBUILDER_CLAUDE_WORKER_MODEL", DEFAULT_WORKER_MODEL
        )
        probe_status, probe_detail = _probe_auth(bin_path, model)
        if probe_status == "unavailable":
            return EXIT_UNAVAILABLE
        if probe_status == "error":
            return _fail(probe_detail)

        timeout = float(os.environ.get("KB_WORKER_TIMEOUT_SECONDS", "3600"))
        rc = _run_model(bin_path, model, _worker_prompt(staged), timeout)
        if rc != 0:
            return _fail(f"claude worker exited {rc}; no fallback to another model")
        if not staged["result"].exists():
            return _fail("claude worker exited 0 without writing the result file")
        try:
            result = _validate_worker_result(staged["result"])
        except (AdapterError, json.JSONDecodeError) as exc:
            return _fail(str(exc))

        shutil.copyfile(staged["result"], _require_env("KB_RESULT_PATH"))
        packet_id = str(json.loads(staged["bundle"].read_text(encoding="utf-8")).get("packet_id", "packet"))
        for path in staged.values():
            path.unlink(missing_ok=True)
        if result["status"] == "completed":
            try:
                _commit_completed_work(task_id, attempt_id, packet_id)
            except AdapterError as exc:
                return _fail(str(exc))
        print(f"Claude worker completed with {model}.")
        return 0
    finally:
        for path in staged.values():
            path.unlink(missing_ok=True)


def _run_review() -> int:
    for name in _REVIEW_REQUIRED_ENV:
        _require_env(name)
    task_id = _require_env("KB_TASK_ID")
    attempt_id = _require_env("KB_ATTEMPT_ID")
    review_sha = _require_env("KB_REVIEW_SHA")
    diff_sha256 = _require_env("KB_REVIEW_DIFF_SHA256")
    try:
        _git_root()
    except AdapterError as exc:
        return _fail(str(exc))

    bin_path = _resolve_claude_bin()
    if bin_path is None:
        return EXIT_UNAVAILABLE

    before = _fingerprint()
    if not before.startswith(review_sha + "\n"):
        return _fail(f"reviewer started on a different HEAD than {review_sha}")

    staged = _stage(attempt_id, ["bundle", "impl", "context", "binding", "review"])
    candidate: Path | None = None
    try:
        try:
            _copy_staged(
                staged,
                {
                    "bundle": "KB_BUNDLE_PATH",
                    "impl": "KB_IMPL_RESULT_PATH",
                    "context": "KB_CONTEXT_MANIFEST_PATH",
                    "binding": "KB_REVIEW_CONTEXT_PATH",
                },
            )
            _validate_review_binding(
                staged["bundle"],
                staged["context"],
                staged["binding"],
                task_id,
                attempt_id,
                review_sha,
                diff_sha256,
            )
        except (AdapterError, json.JSONDecodeError, KeyError) as exc:
            return _fail(str(exc))

        model = os.environ.get(
            "KITTYBUILDER_CLAUDE_REVIEW_MODEL", DEFAULT_REVIEWER_MODEL
        )
        probe_status, probe_detail = _probe_auth(bin_path, model)
        if probe_status == "unavailable":
            return EXIT_UNAVAILABLE
        if probe_status == "error":
            return _fail(probe_detail)

        timeout = float(os.environ.get("KB_REVIEW_TIMEOUT_SECONDS", "900"))
        rc = _run_model(bin_path, model, _reviewer_prompt(staged), timeout)
        if rc != 0:
            return _fail(f"claude reviewer exited {rc}; no fallback to another model")
        if not staged["review"].exists():
            return _fail("claude reviewer exited 0 without writing the review file")
        try:
            review = _validate_review_result(staged["review"])
        except (AdapterError, json.JSONDecodeError) as exc:
            return _fail(str(exc))

        # Reviewer immutability: publish no review artifact unless untouched.
        after = _fingerprint()
        if after != before:
            return _fail("read-only reviewer changed the worktree; no review published")

        note_path = os.environ.get("KB_REVIEW_NOTE_PATH")
        if note_path:
            _write_review_note(review, Path(note_path), review_sha, model)

        import tempfile as _tempfile

        candidate = Path(_tempfile.mkstemp(prefix="kittybuilder-claude-review-")[1])
        candidate.write_text(
            json.dumps(review, indent=2, sort_keys=True), encoding="utf-8"
        )
        shutil.copyfile(candidate, _require_env("KB_REVIEW_RESULT_PATH"))
        print(f"Claude reviewer completed with {model}.")
        return 0
    finally:
        if candidate is not None:
            candidate.unlink(missing_ok=True)
        for path in staged.values():
            path.unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kittybuilder_claude_adapter.py",
        description=__doc__,
    )
    parser.add_argument(
        "mode",
        choices=["worker", "review"],
        help="adapter role: implement (worker) or read-only review",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.mode == "worker":
        return _run_worker()
    return _run_review()


if __name__ == "__main__":
    raise SystemExit(main())
