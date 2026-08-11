#!/usr/bin/env python3
"""KittyBuilder adapter for Codex CLI using ChatGPT authentication."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
TIMEOUT_RUNNER = SCRIPT_DIR / "run_with_timeout.py"
PROVIDER_UNAVAILABLE = 75


def _required(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _git(*args: str, cwd: Path | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=cwd, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fingerprint(cwd: Path, *, reviewer: bool = False) -> tuple[str, str]:
    args = ["status", "--porcelain=v1", "--untracked-files=all"]
    if reviewer:
        args += ["--", ".", ":(exclude).omo/run-continuation/**"]
    return _git("rev-parse", "HEAD", cwd=cwd), _git(*args, cwd=cwd)


def _validate_context(bundle: Path, manifest: Path, task_id: str, attempt_id: str) -> None:
    data = json.loads(manifest.read_text(encoding="utf-8"))
    if data.get("task_id") != task_id or str(data.get("attempt_id")) != attempt_id:
        raise RuntimeError("context manifest task/attempt mismatch")
    digest = hashlib.sha256(bundle.read_bytes()).hexdigest()
    nested = (data.get("context") or {}).get("task_bundle", {}).get("sha256")
    if digest != data.get("bundle_sha256") or digest != nested:
        raise RuntimeError("context bundle hash does not match run manifest")


def _implementation_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "contract_version": {"type": "integer", "const": 1},
            "status": {"type": "string", "enum": ["completed", "failed"]},
            "summary": {"type": "string"},
            "diff_summary": {"type": "string"},
            "validation": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "passed": {"type": "boolean"},
                    "output": {"type": "string"},
                },
                "required": ["passed", "output"],
            },
            "claims": {"type": "array", "items": {"type": "string"}},
        },
        "required": [
            "contract_version",
            "status",
            "summary",
            "diff_summary",
            "validation",
            "claims",
        ],
    }


def _review_schema() -> dict[str, Any]:
    finding = {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "severity": {"type": "string", "enum": ["critical", "major", "minor"]},
            "note": {"type": "string"},
        },
        "required": ["severity", "note"],
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "properties": {
            "contract_version": {"type": "integer", "const": 1},
            "verdict": {
                "type": "string",
                "enum": ["approve", "request_changes", "reject"],
            },
            "summary": {"type": "string"},
            "findings": {"type": "array", "items": finding},
        },
        "required": ["contract_version", "verdict", "summary", "findings"],
    }


def _run_codex(
    cwd: Path,
    *,
    sandbox: str,
    prompt: str,
    schema_path: Path,
    output_path: Path,
    timeout_seconds: int,
    model: str | None,
) -> int:
    codex = shutil.which("codex")
    if codex is None:
        return PROVIDER_UNAVAILABLE
    args = [
        sys.executable,
        str(TIMEOUT_RUNNER),
        str(timeout_seconds),
        codex,
        "exec",
        "--ephemeral",
        "--ignore-user-config",
        "--sandbox",
        sandbox,
        "-C",
        str(cwd),
        "--output-schema",
        str(schema_path),
        "-o",
        str(output_path),
    ]
    if model:
        args += ["--model", model]
    args.append(prompt)
    return subprocess.run(args, cwd=cwd, check=False, stdin=subprocess.DEVNULL).returncode


def _cleanup(paths: list[Path]) -> None:
    for path in paths:
        path.unlink(missing_ok=True)


def _provider_failure(
    *, cwd: Path, before: tuple[str, str], produced_output: bool, reviewer: bool, rc: int
) -> int:
    after = _fingerprint(cwd, reviewer=reviewer)
    if not produced_output and after == before:
        print(f"ERROR: Codex provider unavailable without partial work (exit {rc})", file=sys.stderr)
        return PROVIDER_UNAVAILABLE
    print(f"ERROR: Codex exited {rc} after producing output or worktree changes", file=sys.stderr)
    return 1


def _validate_implementation(path: Path) -> dict[str, Any]:
    result = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(result, dict) or result.get("contract_version") != 1:
        raise RuntimeError("invalid implementation contract")
    if result.get("status") not in {"completed", "failed"}:
        raise RuntimeError("invalid implementation status")
    for key in ("summary", "diff_summary"):
        if not isinstance(result.get(key), str):
            raise RuntimeError(f"invalid implementation {key}")
    validation = result.get("validation")
    if not isinstance(validation, dict):
        raise RuntimeError("invalid validation contract")
    if not isinstance(validation.get("passed"), bool) or not isinstance(validation.get("output"), str):
        raise RuntimeError("invalid validation contract")
    claims = result.get("claims")
    if not isinstance(claims, list) or not all(isinstance(item, str) for item in claims):
        raise RuntimeError("invalid implementation claims")
    return result


def _validate_review(path: Path) -> dict[str, Any]:
    review = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(review, dict) or review.get("contract_version") != 1:
        raise RuntimeError("invalid review contract")
    if review.get("verdict") not in {"approve", "request_changes", "reject"}:
        raise RuntimeError("invalid review verdict")
    if not isinstance(review.get("summary"), str) or not isinstance(review.get("findings"), list):
        raise RuntimeError("invalid review fields")
    for finding in review["findings"]:
        if not isinstance(finding, dict):
            raise RuntimeError("invalid review finding")
        if finding.get("severity") not in {"critical", "major", "minor"}:
            raise RuntimeError("invalid review severity")
        if not isinstance(finding.get("note"), str):
            raise RuntimeError("invalid review note")
    return review


def _worker() -> int:
    cwd = Path.cwd()
    task_id = _required("KB_TASK_ID")
    attempt_id = _required("KB_ATTEMPT_ID")
    bundle_src = Path(_required("KB_BUNDLE_PATH"))
    context_src = Path(_required("KB_CONTEXT_MANIFEST_PATH"))
    result_dst = Path(_required("KB_RESULT_PATH"))
    timeout_seconds = int(_required("KB_WORKER_TIMEOUT_SECONDS"))
    before = _fingerprint(cwd)
    prefix = cwd / f".kittybuilder-codex-{attempt_id}"
    bundle = prefix.with_name(prefix.name + "-bundle.json")
    context = prefix.with_name(prefix.name + "-context.json")
    schema = prefix.with_name(prefix.name + "-schema.json")
    result = prefix.with_name(prefix.name + "-result.json")
    staging = [bundle, context, schema, result]
    if any(path.exists() for path in staging):
        raise RuntimeError("Codex worker staging path already exists")
    try:
        shutil.copy2(bundle_src, bundle)
        shutil.copy2(context_src, context)
        _validate_context(bundle, context, task_id, attempt_id)
        schema.write_text(json.dumps(_implementation_schema()), encoding="utf-8")
        bundle_sha = hashlib.sha256(bundle.read_bytes()).hexdigest()
        context_sha = hashlib.sha256(context.read_bytes()).hexdigest()
    except Exception:
        _cleanup(staging)
        raise
    prompt = f"""You are a KittyBuilder implementation worker in an isolated git worktree.
Read AGENTS.md, .claude/HANDOFF.md, and .claude/STATE.md when present.
Read the staged packet bundle at {bundle} and run manifest at {context}.
Bundle SHA-256: {bundle_sha}; manifest SHA-256: {context_sha}.
Implement only that packet. Stay within allowed paths and acceptance criteria.
Do not push, merge, delete files, touch secrets/env files, or read runner-owned paths.
Run the declared validation commands and focused tests that materially prove the change.
Your final response must be the structured implementation contract required by the output schema.
Use status=failed if implementation or validation cannot honestly pass."""
    model = os.environ.get("KITTYBUILDER_CODEX_MODEL")
    try:
        rc = _run_codex(
            cwd,
            sandbox="workspace-write",
            prompt=prompt,
            schema_path=schema,
            output_path=result,
            timeout_seconds=timeout_seconds,
            model=model,
        )
    except Exception:
        _cleanup(staging)
        raise
    produced = result.exists()
    if rc != 0:
        if rc == 124:
            print(f"WARNING: Codex worker timed out after {timeout_seconds}s", file=sys.stderr)
        _cleanup(staging)
        return _provider_failure(
            cwd=cwd, before=before, produced_output=produced, reviewer=False, rc=rc
        )
    if not result.exists():
        _cleanup(staging)
        return _provider_failure(
            cwd=cwd, before=before, produced_output=False, reviewer=False, rc=0
        )
    try:
        implementation = _validate_implementation(result)
    except Exception:
        _cleanup(staging)
        raise
    result_dst.write_bytes(result.read_bytes())
    _cleanup(staging)
    if implementation["status"] == "completed":
        sanitize = cwd / "scripts" / "sanitize_builder_state.sh"
        if sanitize.exists() and os.access(sanitize, os.X_OK):
            subprocess.run(["bash", str(sanitize)], cwd=cwd, check=True)
        if _git("status", "--porcelain=v1", "--untracked-files=all", cwd=cwd):
            packet_id = json.loads(bundle_src.read_text(encoding="utf-8"))["packet_id"]
            label = model or "codex-default"
            subprocess.run(["git", "add", "-A"], cwd=cwd, check=True)
            subprocess.run(
                [
                    "git",
                    "commit",
                    "--quiet",
                    "-m",
                    f"[{packet_id}] kittybuilder: {task_id} attempt {attempt_id} ({label})",
                ],
                cwd=cwd,
                check=True,
            )
    print(f"Codex worker completed with {model or 'default model'}.")
    return 0


def _reviewer() -> int:
    cwd = Path.cwd()
    task_id = _required("KB_TASK_ID")
    attempt_id = _required("KB_ATTEMPT_ID")
    bundle_src = Path(_required("KB_BUNDLE_PATH"))
    impl_src = Path(_required("KB_IMPL_RESULT_PATH"))
    context_src = Path(_required("KB_CONTEXT_MANIFEST_PATH"))
    binding_src = Path(_required("KB_REVIEW_CONTEXT_PATH"))
    review_dst = Path(_required("KB_REVIEW_RESULT_PATH"))
    review_sha = _required("KB_REVIEW_SHA")
    review_diff = _required("KB_REVIEW_DIFF_SHA256")
    timeout_seconds = int(_required("KB_REVIEW_TIMEOUT_SECONDS"))
    before = _fingerprint(cwd, reviewer=True)
    if before[0] != review_sha:
        raise RuntimeError(f"review HEAD {before[0]} != expected {review_sha}")
    prefix = cwd / f".kittybuilder-codex-review-{attempt_id}"
    bundle = prefix.with_name(prefix.name + "-bundle.json")
    implementation = prefix.with_name(prefix.name + "-impl.json")
    context = prefix.with_name(prefix.name + "-context.json")
    binding = prefix.with_name(prefix.name + "-binding.json")
    schema = prefix.with_name(prefix.name + "-schema.json")
    review = prefix.with_name(prefix.name + "-result.json")
    staging = [bundle, implementation, context, binding, schema, review]
    if any(path.exists() for path in staging):
        raise RuntimeError("Codex reviewer staging path already exists")
    try:
        shutil.copy2(bundle_src, bundle)
        shutil.copy2(impl_src, implementation)
        shutil.copy2(context_src, context)
        shutil.copy2(binding_src, binding)
        _validate_context(bundle, context, task_id, attempt_id)
        binding_data = json.loads(binding.read_text(encoding="utf-8"))
        if (
            binding_data.get("task_id") != task_id
            or str(binding_data.get("attempt_id")) != attempt_id
            or binding_data.get("review_sha") != review_sha
            or binding_data.get("diff_sha256") != review_diff
        ):
            raise RuntimeError("review binding identity mismatch")
        schema.write_text(json.dumps(_review_schema()), encoding="utf-8")
    except Exception:
        _cleanup(staging)
        raise
    prompt = f"""You are an independent read-only KittyBuilder reviewer.
Do not edit, write, commit, push, merge, delete files, or touch secrets.
Read AGENTS.md and these staged local artifacts:
- packet bundle: {bundle}
- implementation result: {implementation}
- run manifest: {context}
- reviewer binding: {binding}
Review HEAD must remain {review_sha}; diff digest must remain {review_diff}.
Inspect the current diff and validation evidence. Run read-only focused checks if useful.
Your final response must be the structured review contract required by the output schema.
Approve only if the packet acceptance criteria and evidence honestly pass."""
    model = os.environ.get("KITTYBUILDER_CODEX_REVIEW_MODEL") or os.environ.get(
        "KITTYBUILDER_CODEX_MODEL"
    )
    try:
        rc = _run_codex(
            cwd,
            sandbox="read-only",
            prompt=prompt,
            schema_path=schema,
            output_path=review,
            timeout_seconds=timeout_seconds,
            model=model,
        )
    except Exception:
        _cleanup(staging)
        raise
    produced = review.exists()
    if rc != 0:
        if rc == 124:
            print(f"WARNING: Codex reviewer timed out after {timeout_seconds}s", file=sys.stderr)
        _cleanup(staging)
        return _provider_failure(
            cwd=cwd, before=before, produced_output=produced, reviewer=True, rc=rc
        )
    if not review.exists():
        _cleanup(staging)
        return _provider_failure(
            cwd=cwd, before=before, produced_output=False, reviewer=True, rc=0
        )
    try:
        review_data = _validate_review(review)
    except Exception:
        _cleanup(staging)
        raise
    review_bytes = review.read_bytes()
    _cleanup(staging)
    after = _fingerprint(cwd, reviewer=True)
    if after != before:
        print("ERROR: read-only Codex reviewer changed the worktree", file=sys.stderr)
        return 1
    review_dst.write_bytes(review_bytes)
    note_path = os.environ.get("KB_REVIEW_NOTE_PATH")
    if note_path:
        lines = [
            "# KittyBuilder review note",
            "",
            f"- Reviewed commit: `{review_sha}`",
            f"- Verdict: {review_data['verdict']}",
            "- Provider: Codex CLI (ChatGPT auth)",
            "",
            "## Summary",
            "",
            str(review_data["summary"]),
        ]
        if review_data["findings"]:
            lines += ["", "## Findings", ""]
            lines += [
                f"- [{item['severity']}] {item['note']}"
                for item in review_data["findings"]
            ]
        Path(note_path).write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"Codex reviewer completed with {model or 'default model'}.")
    return 0


def main() -> int:
    if len(sys.argv) != 2 or sys.argv[1] not in {"worker", "reviewer"}:
        print("usage: kittybuilder_codex_adapter.py {worker|reviewer}", file=sys.stderr)
        return 2
    try:
        if sys.argv[1] == "worker":
            return _worker()
        return _reviewer()
    except (RuntimeError, ValueError, OSError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
