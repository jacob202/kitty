"""Weekly evidence guard against infrastructure work displacing Kitty product gain."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from typing import Any

PRODUCT_PREFIXES = (
    "gateway/kitty-chat/src/",
    "gateway/routes/",
    "gateway/image_",
    "gateway/knowledge.py",
    "gateway/journal_store.py",
    "gateway/memory",
    "gateway/project_store.py",
    "gateway/todo_store.py",
    "gateway/voice_middleware.py",
)
INFRA_PREFIXES = (
    ".agents/",
    ".claude/",
    ".github/",
    "coordination/",
    "gateway/agent_coordination",
    "gateway/builder_",
    "mcp/builder/",
    "scripts/",
)
# Attention floor, not a productivity KPI: at least one product-touch commit
# per four infrastructure-only commits before self-inventing more infrastructure.
DEFAULT_MIN_PRODUCT_RATIO = 0.20


class GuardError(RuntimeError):
    pass


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo), *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise GuardError(proc.stderr.strip() or "git command failed")
    return proc.stdout


def _matches(path: str, prefixes: tuple[str, ...]) -> bool:
    return any(path.startswith(prefix) for prefix in prefixes)


def _recent_commits(repo: Path, since_days: int) -> list[dict[str, Any]]:
    if since_days < 1:
        raise GuardError("since_days must be at least 1")
    raw = _git(
        repo,
        "log",
        f"--since={since_days}.days.ago",
        "--format=@@%H%x09%s",
        "--name-only",
        "--no-merges",
    )
    commits: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in raw.splitlines():
        if line.startswith("@@"):
            if current is not None:
                commits.append(current)
            sha, subject = line[2:].split("\t", 1)
            current = {"sha": sha, "subject": subject, "paths": []}
        elif line and current is not None:
            current["paths"].append(line)
    if current is not None:
        commits.append(current)
    return commits


def analyze_repo(
    repo: Path,
    *,
    since_days: int = 7,
    minimum_product_ratio: float = DEFAULT_MIN_PRODUCT_RATIO,
) -> dict[str, Any]:
    if not 0.0 <= minimum_product_ratio <= 1.0:
        raise GuardError("minimum_product_ratio must be between 0 and 1")
    commits = _recent_commits(repo, since_days)
    product: list[dict[str, Any]] = []
    infra_only: list[dict[str, Any]] = []
    other: list[dict[str, Any]] = []

    for commit in commits:
        paths = commit["paths"]
        product_paths = [p for p in paths if _matches(p, PRODUCT_PREFIXES)]
        infra_paths = [p for p in paths if _matches(p, INFRA_PREFIXES)]
        item = {
            "sha": commit["sha"],
            "subject": commit["subject"],
            "product_paths": product_paths,
            "infrastructure_paths": infra_paths,
        }
        if product_paths:
            product.append(item)
        elif infra_paths:
            infra_only.append(item)
        else:
            other.append(item)

    relevant_count = len(product) + len(infra_only)
    product_ratio = len(product) / relevant_count if relevant_count else 1.0
    needs_product_answer = bool(infra_only) and product_ratio < minimum_product_ratio
    return {
        "window_days": since_days,
        "commit_count": len(commits),
        "relevant_commit_count": relevant_count,
        "product_touch_commits": product,
        "infrastructure_only_commits": infra_only,
        "other_commits": other,
        "product_ratio": product_ratio,
        "minimum_product_ratio": minimum_product_ratio,
        "needs_product_answer": needs_product_answer,
        "status": (
            "needs_product_answer"
            if needs_product_answer
            else "product_evidence_present"
            if product
            else "no_relevant_commits"
        ),
        "note": (
            "Path evidence identifies candidate product gain; it does not prove "
            "the user-visible outcome worked. Verify at least one actual journey."
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--since-days", type=int, default=7)
    parser.add_argument(
        "--min-product-ratio",
        type=float,
        default=DEFAULT_MIN_PRODUCT_RATIO,
        help="minimum product-touch share among product/infrastructure commits",
    )
    parser.add_argument("--json", action="store_true")
    parser.add_argument(
        "--enforce",
        action="store_true",
        help="exit 2 when the recent product-touch ratio is below the floor",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = analyze_repo(
            args.repo.resolve(),
            since_days=args.since_days,
            minimum_product_ratio=args.min_product_ratio,
        )
    except GuardError as exc:
        print(f"product-gain-guard: {exc}")
        return 1

    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(
            f"product-gain-guard: {result['status']} "
            f"({len(result['product_touch_commits'])} product-touch, "
            f"{len(result['infrastructure_only_commits'])} infrastructure-only, "
            f"ratio={result['product_ratio']:.1%}, "
            f"floor={result['minimum_product_ratio']:.1%})"
        )
        for item in result["product_touch_commits"][:5]:
            print(f"  product evidence {item['sha'][:8]} {item['subject']}")
        if result["needs_product_answer"]:
            print(
                "  product-touch share is below the weekly floor; answer what the "
                "product gained before admitting more infrastructure-only work"
            )

    if args.enforce and result["needs_product_answer"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
