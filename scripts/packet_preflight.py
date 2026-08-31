#!/usr/bin/env python3
"""Check a Builder packet manifest for the defects that have actually stopped runs.

Read-only. Mutates nothing, inspects no Builder state, and is not a second
control plane — it answers one question: would this packet waste an attempt?

Rules and the failures behind them are documented in
``docs/packets/PACKET_STANDARD.md``. Run this before
``kitty builder initiative validate``; that command owns schema and dependency
integrity, this one owns authoring defects the schema cannot see.

    python scripts/packet_preflight.py docs/initiatives/foo.json
    python scripts/packet_preflight.py --all

Exit 0 when every checked manifest is clean, 1 when any error is found.
Warnings never fail the run.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INITIATIVES = ROOT / "docs" / "initiatives"

MANIFEST_KEYS = {"manifest_version", "initiative_id", "title", "description", "packets"}
PACKET_KEYS = {
    "id",
    "title",
    "objective",
    "depends_on",
    "acceptance_criteria",
    "allowed_paths",
    "policy",
    "validation_commands",
}

# Paths a Builder worker must never be allowed to change. Continuity files are
# session state, data/logs are runtime truth, and CI/secrets are Jacob's alone.
FORBIDDEN_PREFIXES = (
    ".claude/",
    ".github/workflows/",
    "data/",
    "logs/",
    ".env",
    "config/action_tiers.json",
)

# The worker shell has no python3.N on PATH; the runner exposes the repo venv as
# plain `python`. A pinned interpreter burns the whole time budget not being
# found — see PACKET_STANDARD.md F2.
PINNED_INTERPRETER = re.compile(r"\bpython3\.\d+\b")

# `npm run <script>` exits 194 silently in this repo and reports a success it
# never proved — docs/packets/014-make-the-gates-honest.md.
NPM_RUN = re.compile(r"\bnpm\s+run\b")

# A Builder worktree is a git worktree, and node_modules/ is gitignored, so it
# is simply absent — verified in .worktrees/kittybuilder/kb_mtgatvyi_340e. The
# runner exposes the Python venv to workers but has no equivalent for Node, so
# every npx/npm gate fails or tries to reach the network from inside the
# sandbox. Frontend proof belongs in the companion doc's Tier 2, run by CI.
NODE_TOOLING = re.compile(r"\b(npx|npm)\b")

# Deliberately broad and stem-matched. A false positive costs one directory
# entry; a false negative costs a burned attempt and a permanently blocked task.
CREATION_VERBS = re.compile(
    r"\b(add|creat|introduc|implement|build|expos|writ|generat|author|"
    r"mak|show|surfac|render|support|wire|provid|emit|persist)",
    re.IGNORECASE,
)

COMMAND_PATH = re.compile(r"(?<![\w./-])((?:[\w.-]+/)+[\w.*-]+)")


class Finding:
    def __init__(self, level: str, packet: str, message: str) -> None:
        self.level = level
        self.packet = packet
        self.message = message

    def __str__(self) -> str:
        where = f"{self.packet}: " if self.packet else ""
        return f"  {self.level:<5} {where}{self.message}"


def display_path(path: Path) -> str:
    """Repo-relative when the manifest lives here, absolute when it does not."""
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def tracked_paths() -> set[str]:
    """Every path in HEAD. The worker branches from a commit, so the dirty
    working tree is the wrong thing to test membership against."""
    try:
        out = subprocess.run(
            ["git", "ls-tree", "-r", "HEAD", "--name-only"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except (subprocess.CalledProcessError, FileNotFoundError):
        return set()
    return {line for line in out.splitlines() if line}


def path_kind(path: str, tracked: set[str]) -> str:
    """'file' if HEAD has it, 'dir' if HEAD has anything under it, else 'new'."""
    cleaned = path.rstrip("/")
    if cleaned in tracked:
        return "file"
    prefix = cleaned + "/"
    if any(entry.startswith(prefix) for entry in tracked):
        return "dir"
    return "new"


def subsystem(path: str) -> str:
    """The fence a new file would need. Two components where the first is a
    container of subprojects, otherwise one."""
    parts = path.rstrip("/").split("/")
    if len(parts) >= 2 and parts[0] == "gateway" and parts[1] == "kitty-chat":
        return "gateway/kitty-chat"
    return parts[0]


def is_test_path(path: str) -> bool:
    return "test" in path.lower() or path.startswith("tests")


CD_PREFIX = re.compile(r"^\s*cd\s+([\w./-]+)\s*&&\s*")


def command_targets(command: str) -> list[str]:
    """Repo-relative paths a validation command names.

    A command may start `cd gateway/kitty-chat && ...`, after which its paths
    are relative to that directory, not the repository root.
    """
    base = ""
    match = CD_PREFIX.match(command)
    if match:
        base = match.group(1).rstrip("/") + "/"
        command = command[match.end() :]

    targets = []
    for found in COMMAND_PATH.finditer(command):
        token = found.group(1)
        if token.startswith(("http", "-")) or "node_modules" in token:
            continue
        targets.append(base + token)
    return targets


def check_packet(
    packet: dict,
    *,
    tracked: set[str],
    seen_ids: dict[str, str],
    manifest_name: str,
) -> list[Finding]:
    findings: list[Finding] = []
    pid = str(packet.get("id") or "<no id>")

    unknown = set(packet) - PACKET_KEYS
    if unknown:
        findings.append(
            Finding("ERROR", pid, f"unknown packet keys {sorted(unknown)} — the validator rejects these")
        )

    if pid in seen_ids:
        findings.append(
            Finding("ERROR", pid, f"packet id already used in {seen_ids[pid]} — ids are globally unique and never reused")
        )
    else:
        seen_ids[pid] = manifest_name

    allowed = [str(p) for p in (packet.get("allowed_paths") or [])]
    criteria = packet.get("acceptance_criteria") or []
    commands = [str(c) for c in (packet.get("validation_commands") or [])]
    objective = str(packet.get("objective") or "")

    if not allowed:
        findings.append(Finding("ERROR", pid, "allowed_paths is empty — the worker can change nothing"))
    if not criteria:
        findings.append(Finding("ERROR", pid, "acceptance_criteria is empty — 'done' is undefined"))
    if not commands:
        findings.append(Finding("ERROR", pid, "validation_commands is empty — nothing proves the change"))

    for path in allowed:
        for bad in FORBIDDEN_PREFIXES:
            if path == bad.rstrip("/") or path.startswith(bad):
                findings.append(Finding("ERROR", pid, f"allowed_path {path!r} is off limits to Builder workers"))

    # F1: a packet whose production fence holds no directory cannot absorb a new
    # file, and the worker writes one anyway — a non-repairable scope violation.
    # A named new file is not enough: V6 named one and still died, because the
    # worker reasonably chose a different filename for the same module.
    prod = [p for p in allowed if not is_test_path(p)]
    if prod:
        creates = bool(CREATION_VERBS.search(objective)) or any(
            CREATION_VERBS.search(str(c)) for c in criteria
        )
        by_subsystem: dict[str, list[str]] = {}
        for path in prod:
            by_subsystem.setdefault(subsystem(path), []).append(path)
        for sub, paths in sorted(by_subsystem.items()):
            if any(path_kind(p, tracked) == "dir" for p in paths):
                continue
            findings.append(
                Finding(
                    "ERROR" if creates else "WARN",
                    pid,
                    f"no allowed path under {sub!r} is a directory ({', '.join(sorted(paths))}), so "
                    "the worker cannot create any new file there — whatever it writes lands outside "
                    "the fence and blocks the task permanently. Allow the directory, or state in the "
                    "companion doc that this packet creates no new files.",
                )
            )

    if not any(is_test_path(p) for p in allowed):
        findings.append(
            Finding("WARN", pid, "no test path in allowed_paths — the packet forbids writing its own proof")
        )

    for command in commands:
        if PINNED_INTERPRETER.search(command):
            findings.append(
                Finding("ERROR", pid, f"validation command pins an interpreter version: {command!r} — use 'python'")
            )
        if NPM_RUN.search(command):
            findings.append(
                Finding("ERROR", pid, f"validation command uses 'npm run': {command!r} — it exits 194 silently")
            )
        elif NODE_TOOLING.search(command):
            findings.append(
                Finding(
                    "ERROR",
                    pid,
                    f"validation command needs Node tooling: {command!r} — a Builder worktree has no "
                    "node_modules (it is gitignored) and the runner exposes no Node toolchain, so this "
                    "gate cannot run. Move the frontend proof to the companion doc's Tier 2 for CI, and "
                    "leave Builder the Python gates it can actually execute.",
                )
            )
        for target in command_targets(command):
            if path_kind(target, tracked) != "new":
                continue
            if any(target == p or target.startswith(p.rstrip("/") + "/") for p in allowed):
                continue
            if "*" in target:
                continue
            findings.append(
                Finding(
                    "ERROR",
                    pid,
                    f"validation command names {target!r}, which does not exist and is not inside "
                    "allowed_paths — this gate can never pass",
                )
            )

    policy = packet.get("policy") or {}
    routing = policy.get("routing")
    if isinstance(routing, dict):
        # A present routing key must be a non-empty string; explicit nulls read
        # as "no preference" but the validator rejects the manifest outright.
        blank = sorted(k for k, v in routing.items() if not isinstance(v, str) or not v.strip())
        if blank:
            findings.append(
                Finding(
                    "ERROR",
                    pid,
                    f"policy.routing has empty value(s) for {blank} — the Builder validator rejects "
                    "this. Omit 'routing' entirely for free work.",
                )
            )
        elif routing:
            findings.append(
                Finding("WARN", pid, f"packet requests paid routing {routing} — the companion doc must justify the spend")
            )

    depends = packet.get("depends_on") or []
    if pid in depends:
        findings.append(Finding("ERROR", pid, "packet depends on itself"))

    return findings


def check_manifest(path: Path, *, tracked: set[str], seen_ids: dict[str, str]) -> list[Finding]:
    findings: list[Finding] = []
    try:
        manifest = json.loads(path.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        return [Finding("ERROR", "", f"cannot read manifest: {exc}")]

    if not isinstance(manifest, dict):
        return [Finding("ERROR", "", "manifest is not an object")]

    if "packets" not in manifest:
        return [Finding("SKIP", "", "no 'packets' key — not a Builder manifest")]

    unknown = set(manifest) - MANIFEST_KEYS
    if unknown:
        findings.append(Finding("ERROR", "", f"unknown top-level keys {sorted(unknown)} — the validator rejects these"))

    packets = manifest.get("packets") or []
    if not packets:
        findings.append(Finding("ERROR", "", "manifest declares no packets"))

    for packet in packets:
        if isinstance(packet, dict):
            findings.extend(
                check_packet(packet, tracked=tracked, seen_ids=seen_ids, manifest_name=path.name)
            )

    # Two packets that can run concurrently must not share a fence.
    for i, a in enumerate(packets):
        if not isinstance(a, dict):
            continue
        for b in packets[i + 1 :]:
            if not isinstance(b, dict):
                continue
            if a.get("id") in (b.get("depends_on") or []) or b.get("id") in (a.get("depends_on") or []):
                continue
            shared = {str(p) for p in (a.get("allowed_paths") or [])} & {
                str(p) for p in (b.get("allowed_paths") or [])
            }
            if shared:
                findings.append(
                    Finding(
                        "WARN",
                        f"{a.get('id')} / {b.get('id')}",
                        f"share allowed_paths {sorted(shared)} with no dependency between them — they can collide",
                    )
                )

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("manifests", nargs="*", type=Path, help="manifest files to check")
    parser.add_argument("--all", action="store_true", help="check every manifest in docs/initiatives/")
    args = parser.parse_args()

    if args.all:
        targets = sorted(INITIATIVES.glob("*.json"))
    elif args.manifests:
        targets = args.manifests
    else:
        parser.error("pass manifest paths or --all")
        return 2

    tracked = tracked_paths()
    if not tracked:
        print("WARNING: could not read HEAD; path-existence checks are disabled", file=sys.stderr)

    seen_ids: dict[str, str] = {}
    errors = 0
    warnings = 0

    for target in targets:
        findings = check_manifest(target, tracked=tracked, seen_ids=seen_ids)
        real = [f for f in findings if f.level != "SKIP"]
        if not real:
            continue
        print(f"\n{display_path(target)}")
        for finding in real:
            print(finding)
            if finding.level == "ERROR":
                errors += 1
            elif finding.level == "WARN":
                warnings += 1

    print(f"\n{len(targets)} manifest(s) checked: {errors} error(s), {warnings} warning(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
