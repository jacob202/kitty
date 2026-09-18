#!/usr/bin/env python3
"""Compile a Git-bound receipt for a governed prompt experiment.

This tool is intentionally read-only. It compares exact committed versions of
one prompt-bearing file, evaluates matched task scores through Kitty's existing
session-learning evaluator, and emits rollback/provenance evidence. It never
activates a candidate, edits a prompt, or creates a second learning store.
"""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Mapping

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.session_learning import SignalError, compare_capability_runs

SCHEMA_VERSION = 1

class PromptExperimentError(ValueError):
    """Raised when provenance or experiment inputs are invalid."""

def _git(repo: Path, *args: str, text: bool = True) -> str | bytes:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], capture_output=True, check=False, text=text
    )
    if result.returncode != 0:
        stderr = result.stderr.strip() if text else result.stderr.decode(errors="replace").strip()
        raise PromptExperimentError(
            f"git {' '.join(args)} failed with exit {result.returncode}: {stderr}"
        )
    return result.stdout

def _resolve_commit(repo: Path, ref: str) -> str:
    if not isinstance(ref, str) or not ref.strip():
        raise PromptExperimentError("Git ref must be a non-empty string")
    value = _git(repo, "rev-parse", "--verify", f"{ref.strip()}^{{commit}}")
    assert isinstance(value, str)
    sha = value.strip()
    if len(sha) != 40:
        raise PromptExperimentError(f"Git ref {ref!r} did not resolve to a full commit SHA")
    return sha

def _normalize_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise PromptExperimentError("path must be a non-empty repository-relative path")
    candidate = Path(path.strip())
    if candidate.is_absolute() or ".." in candidate.parts:
        raise PromptExperimentError("path must stay inside the repository")
    normalized = candidate.as_posix().lstrip("./")
    if not normalized or normalized.startswith(".git/"):
        raise PromptExperimentError("path must name a tracked prompt-bearing file")
    return normalized

def _blob(repo: Path, sha: str, path: str) -> bytes:
    value = _git(repo, "show", f"{sha}:{path}", text=False)
    assert isinstance(value, bytes)
    return value

def compile_receipt(
    *,
    repo: Path,
    path: str,
    baseline_ref: str,
    candidate_ref: str,
    baseline_scores: Mapping[str, Any],
    candidate_scores: Mapping[str, Any],
    minimum_lift: float,
    context: Mapping[str, Any],
) -> dict[str, Any]:
    repo = repo.resolve()
    try:
        _git(repo, "rev-parse", "--git-dir")
    except PromptExperimentError as exc:
        raise PromptExperimentError(f"not a Git repository: {repo}") from exc
    prompt_path = _normalize_path(path)
    baseline_sha = _resolve_commit(repo, baseline_ref)
    candidate_sha = _resolve_commit(repo, candidate_ref)
    baseline = _blob(repo, baseline_sha, prompt_path)
    candidate = _blob(repo, candidate_sha, prompt_path)
    if baseline == candidate:
        raise PromptExperimentError(
            "baseline and candidate prompt content are identical; there is no experiment delta"
        )
    try:
        baseline_text = baseline.decode("utf-8")
        candidate_text = candidate.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptExperimentError("prompt experiment files must be UTF-8 text") from exc
    try:
        evaluation = compare_capability_runs(
            baseline_scores,
            candidate_scores,
            minimum_lift=minimum_lift,
            context=context,
        )
    except SignalError as exc:
        raise PromptExperimentError(str(exc)) from exc
    diff = "".join(
        difflib.unified_diff(
            baseline_text.splitlines(keepends=True),
            candidate_text.splitlines(keepends=True),
            fromfile=f"{prompt_path}@{baseline_sha[:12]}",
            tofile=f"{prompt_path}@{candidate_sha[:12]}",
        )
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "artifact_type": "prompt_experiment_receipt",
        "prompt_path": prompt_path,
        "baseline": {
            "requested_ref": baseline_ref,
            "commit_sha": baseline_sha,
            "content_sha256": hashlib.sha256(baseline).hexdigest(),
        },
        "candidate": {
            "requested_ref": candidate_ref,
            "commit_sha": candidate_sha,
            "content_sha256": hashlib.sha256(candidate).hexdigest(),
        },
        "diff": diff,
        "evaluation": evaluation,
        "promotion_evidence": "supported" if evaluation["improved"] else "not_supported",
        "activation": {
            "authorized": False,
            "reason": "receipt is evidence only; promotion requires existing Git/Builder authority",
        },
        "rollback": {"commit_sha": baseline_sha, "prompt_path": prompt_path},
    }

def _json_object(raw: str, *, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise PromptExperimentError(f"{label} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise PromptExperimentError(f"{label} must be a JSON object")
    return value

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--path", required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--baseline-scores-json", required=True)
    parser.add_argument("--candidate-scores-json", required=True)
    parser.add_argument("--minimum-lift", type=float, default=0.0)
    parser.add_argument("--model", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--scorer", required=True)
    return parser

def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        receipt = compile_receipt(
            repo=args.repo,
            path=args.path,
            baseline_ref=args.baseline_ref,
            candidate_ref=args.candidate_ref,
            baseline_scores=_json_object(args.baseline_scores_json, label="baseline scores"),
            candidate_scores=_json_object(args.candidate_scores_json, label="candidate scores"),
            minimum_lift=args.minimum_lift,
            context={"model": args.model, "workspace": args.workspace, "scorer": args.scorer},
        )
    except PromptExperimentError as exc:
        print(f"prompt experiment error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
