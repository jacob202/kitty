#!/usr/bin/env python3
"""Run a candidate review model against a frozen Codex review unit.

This is the producing half of the Codex review-fidelity eval. It reconstructs the
exact diff a Codex finding was made against, asks a candidate model to review that
diff under the same strict standard, and records the candidate's findings as
observations for ``score.py``.

The harness is deliberately endpoint-agnostic: anything that speaks the
OpenAI-compatible ``/v1/chat/completions`` shape works. That includes a local
llama.cpp server, Ollama, and a hosted router. Which endpoint and model produced
a set of observations is recorded in the output, because a fidelity score is only
meaningful together with the model that earned it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.pr_review import _review_chunks  # noqa: E402

NO_FINDINGS = "NO_ACTIONABLE_FINDINGS"

# A reasoning model spends most of its budget on chain-of-thought before it emits the
# JSON answer, so a small cap truncates the response mid-thought and yields no findings
# at all. This default leaves room for reasoning plus the array; raise it for models
# that reason at length.
DEFAULT_MAX_TOKENS = 16000

SYSTEM_PROMPT = """You are a strict independent code reviewer. Review only the supplied diff.

A reportable finding must be supported by the diff and must identify all four:
- name the changed file and identify the changed behavior/hunk
- the exact input, state, sequence, or concurrency condition that reaches the defect
- the specific failure mode: the exact incorrect observable outcome (wrong state, false success, data loss, security boundary break, crash, or user-visible regression)
- the smallest corrective action

Do not report speculative or generic review noise. In particular, do not report a finding
whose reasoning is merely that something *may*, *might*, *could*, or *potentially* fail,
or whose action is only to "ensure", "consider", "verify", "monitor", add comments,
add unspecified tests, or clarify documentation. Missing tests are not themselves a defect.
Configuration is not a defect unless the supplied diff creates a concrete broken configuration.
If you cannot name the exact input/state and exact wrong outcome, omit the finding.

Prioritize correctness, authorization, false-success states, retry/recovery races, stale evidence,
data loss, resource leaks with a concrete trigger, and user-visible failure/recovery behavior.
Do not repeat the PR summary. Remove any finding that is not directly grounded in changed code
shown in this chunk.

Severity is P1 for a defect that breaks correctness, data, security, or a user's ability to
complete the task, and P2 for a real defect with narrower reach.

Respond with a JSON array and nothing else. Each element must be an object with exactly:
  "path"     - the changed file path the finding sits in
  "line"     - the 1-based line number in the file's NEW version, or null if not locatable
  "severity" - "P1" or "P2"
  "title"    - one short imperative line naming the defect
  "detail"   - 2-4 sentences: the trigger, the exact wrong outcome, and the corrective action

If there are no actionable findings, respond with exactly:
NO_ACTIONABLE_FINDINGS
"""

_DECODER = json.JSONDecoder()


class EndpointError(RuntimeError):
    """Raised when the candidate endpoint cannot complete a review request."""


def _git(*args: str) -> str:
    completed = subprocess.run(
        ["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    if completed.returncode != 0:
        raise RuntimeError(
            f"git {' '.join(args)} failed ({completed.returncode}): {completed.stderr.strip()}"
        )
    return completed.stdout


def _present(revision: str) -> bool:
    completed = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=False,
    )
    return completed.returncode == 0


def ensure_revision(revision: str, *, pr: int) -> bool:
    """Make a reviewed revision available, fetching its PR ref when Git lacks it.

    A merged-and-deleted branch can leave the reviewed head unreachable from any
    local ref. GitHub still serves it under ``refs/pull/<n>/head``, so fetch that
    specific ref. Returns True when a fetch was needed, and raises the underlying
    Git error when the revision cannot be obtained at all.
    """
    if _present(revision):
        return False
    print(
        f"PR {pr}: revision {revision[:12]} is absent locally; fetching refs/pull/{pr}/head",
        file=sys.stderr,
    )
    _git("fetch", "--quiet", "origin", f"refs/pull/{pr}/head")
    if not _present(revision):
        raise RuntimeError(
            f"PR {pr}: revision {revision} is unavailable locally and refs/pull/{pr}/head "
            "did not provide it; the review unit cannot be reproduced"
        )
    return True


def review_unit_diff(base: str, head: str, *, pr: int | None = None) -> str:
    """Reconstruct exactly what the reviewer saw: the PR's diff at its reviewed head."""
    for revision in (base, head):
        if not re.fullmatch(r"[0-9a-f]{40}", revision or ""):
            raise ValueError(f"review unit revision must be a full 40-char SHA: {revision!r}")
    if pr is not None:
        for revision in (base, head):
            ensure_revision(revision, pr=pr)
    return _git("diff", "--no-color", f"{base}...{head}")


def _chat(
    endpoint: str,
    model: str,
    api_key: str | None,
    prompt: str,
    timeout: float,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> str:
    payload = json.dumps(
        {
            "model": model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": max_tokens,
        }
    ).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    request = Request(
        f"{endpoint.rstrip('/')}/v1/chat/completions", data=payload, headers=headers, method="POST"
    )
    try:
        with urlopen(request, timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:400]
        raise EndpointError(
            f"{endpoint} returned HTTP {exc.code} for model {model}: {detail}"
        ) from exc
    except URLError as exc:
        raise EndpointError(f"{endpoint} unreachable for model {model}: {exc.reason}") from exc
    try:
        return str(body["choices"][0]["message"]["content"])
    except (KeyError, IndexError, TypeError) as exc:
        raise EndpointError(
            f"{endpoint} returned an unusable payload for model {model}: {json.dumps(body)[:400]}"
        ) from exc


def _json_arrays(text: str) -> list[list[Any]]:
    """Every well-formed JSON array in the text, in order of appearance.

    A reasoning model narrates before it answers, and narration can itself contain
    brackets. Scanning for balanced arrays with a real decoder (rather than a
    greedy ``\\[.*\\]``) avoids splicing prose into the payload; the caller then
    prefers the last well-formed array, which is where the answer lands.
    """
    arrays: list[list[Any]] = []
    for index, char in enumerate(text):
        if char != "[":
            continue
        try:
            value, _ = _DECODER.raw_decode(text, index)
        except ValueError:
            continue
        if isinstance(value, list):
            arrays.append(value)
    return arrays


def parse_findings(text: str) -> list[dict[str, Any]]:
    """Extract the candidate's structured findings, tolerating prose around the array."""
    stripped = text.strip()
    arrays = _json_arrays(stripped)
    if not arrays:
        # The sentinel is only honoured when there is no array at all: a model that
        # reasons out loud may echo the instruction text (which contains the sentinel)
        # before reporting real findings, and treating that echo as "no findings" would
        # silently zero out a genuine review.
        if NO_FINDINGS in stripped:
            return []
        raise ValueError(
            f"candidate returned neither a JSON array nor the no-findings sentinel "
            f"({len(stripped)} chars): {stripped[:200]!r}"
        )
    payload = arrays[-1]
    # Accept only an array that could actually be an answer. Prose from a reasoning
    # model frequently contains incidental brackets ("files [a.py, b.py]"), and
    # treating one of those as the result would report a confident zero findings
    # for a run that in fact found defects -- a silent false negative, which is the
    # most damaging failure this eval could have. Refusing is the honest outcome.
    if payload and not all(isinstance(item, dict) and item.get("path") for item in payload):
        raise ValueError(
            f"candidate's final JSON array is not a findings list ({len(payload)} items, "
            f"first={payload[0]!r}); response is prose or a different structure "
            f"({len(stripped)} chars): {stripped[-200:]!r}"
        )
    findings: list[dict[str, Any]] = []
    for item in payload:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        findings.append(
            {
                "path": str(item["path"]).lstrip("./"),
                "line": item.get("line") if isinstance(item.get("line"), int) else None,
                "severity": str(item.get("severity") or "unknown").upper(),
                "title": " ".join(str(item.get("title") or "").split()),
                "detail": " ".join(str(item.get("detail") or "").split()),
            }
        )
    return findings


def detect_unit(
    unit: dict[str, Any],
    *,
    endpoint: str,
    model: str,
    api_key: str | None,
    timeout: float,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict[str, Any]:
    diff = review_unit_diff(unit["base"], unit["head"], pr=unit["pr"])
    if not diff.strip():
        raise RuntimeError(f"PR {unit['pr']} produced an empty diff from {unit['base']}...{unit['head']}")
    chunks = _review_chunks(diff)
    findings: list[dict[str, Any]] = []
    errors: list[str] = []
    for index, chunk in enumerate(chunks):
        prompt = (
            f"Repository: jacob202/kitty\nPR #{unit['pr']}: {unit.get('title') or ''}\n"
            f"This is diff chunk {index + 1} of {len(chunks)}. Review only this chunk.\n\n"
            f"```diff\n{chunk}\n```"
        )
        try:
            findings.extend(
                parse_findings(_chat(endpoint, model, api_key, prompt, timeout, max_tokens))
            )
        except (EndpointError, ValueError) as exc:
            # A failed chunk is recorded, never silently dropped: a partial run must
            # not look like a candidate that simply found nothing.
            errors.append(f"chunk {index + 1}/{len(chunks)}: {exc}")
    return {
        "pr": unit["pr"],
        "base": unit["base"],
        "head": unit["head"],
        "diff_sha256": hashlib.sha256(diff.encode("utf-8")).hexdigest(),
        "diff_chars": len(diff),
        "chunks": len(chunks),
        "findings": findings,
        "chunk_errors": errors,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--endpoint", default=os.environ.get("CODEX_EVAL_ENDPOINT", "http://127.0.0.1:8080"))
    parser.add_argument("--model", default=os.environ.get("CODEX_EVAL_MODEL"))
    parser.add_argument("--api-key-env", default="CODEX_EVAL_API_KEY")
    parser.add_argument("--prs", default="", help="comma-separated PR numbers; default is the whole corpus")
    parser.add_argument("--timeout", type=float, default=300.0)
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=int(os.environ.get("CODEX_EVAL_MAX_TOKENS", DEFAULT_MAX_TOKENS)),
        help="completion budget; reasoning models spend most of it on chain-of-thought first",
    )
    args = parser.parse_args()

    if not args.model:
        print("--model (or CODEX_EVAL_MODEL) is required", file=sys.stderr)
        return 2

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    if corpus.get("version") != 1:
        print("unsupported corpus version", file=sys.stderr)
        return 2

    wanted = {int(item) for item in args.prs.split(",") if item.strip()} if args.prs else None
    units = [u for u in corpus["review_units"] if wanted is None or u["pr"] in wanted]
    if not units:
        print("no review units selected", file=sys.stderr)
        return 2

    api_key = os.environ.get(args.api_key_env) or None
    results: list[dict[str, Any]] = []
    failures = 0
    for unit in units:
        started = time.monotonic()
        try:
            result = detect_unit(
                unit,
                endpoint=args.endpoint,
                model=args.model,
                api_key=api_key,
                timeout=args.timeout,
                max_tokens=args.max_tokens,
            )
        except (RuntimeError, ValueError) as exc:
            failures += 1
            print(f"PR {unit['pr']}: FAILED: {exc}", file=sys.stderr)
            continue
        result["elapsed_seconds"] = round(time.monotonic() - started, 1)
        results.append(result)
        print(
            f"PR {unit['pr']}: {len(result['findings'])} candidate findings, "
            f"{len(result['chunk_errors'])} chunk errors, {result['elapsed_seconds']}s",
            file=sys.stderr,
        )

    if failures:
        print(f"{failures} review unit(s) failed outright", file=sys.stderr)

    observations = {
        "corpus_version": corpus["version"],
        "provenance": {
            "endpoint": args.endpoint,
            "model": args.model,
            "max_tokens": args.max_tokens,
            "api_key_env": args.api_key_env if api_key else None,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "review_units_requested": len(units),
            "review_units_completed": len(results),
            "review_units_failed": failures,
        },
        "review_units": {str(r["pr"]): r for r in results},
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(observations, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.out}", file=sys.stderr)
    return 0 if results else 1


if __name__ == "__main__":
    raise SystemExit(main())
