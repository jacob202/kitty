#!/usr/bin/env python3.12
"""Resumable campaign ledger — survives usage limits, crashes, and API errors.

A campaign is a long multi-phase task. The ledger (``docs/campaigns/<slug>.md``)
is the durable state: every phase carries the exact command that proves it and
the commit SHA that command passed at. A fresh session runs ``resume`` and
re-derives its position instead of re-litigating context.

Why a script and not a prompt: "mark verified only when tests pass" is
unenforceable as prose — a model can narrate past it. Here ``verify`` is the
only writer of ``verified``, and it refuses without both a passing command and
a real commit. ``audit`` catches a ledger that lies after the fact.

This is a per-campaign phase ledger, not a second backlog. Session continuity
still belongs to .claude/STATE.md and .claude/HANDOFF.md (ADR/CLAUDE.md §9);
docs/ROADMAP.md remains the only roadmap.

ponytail: strict markdown pipe table, stdlib only. Fails loud on a malformed
ledger rather than guessing — a silently mis-parsed ledger is worse than none.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

STATUSES = ("pending", "in-progress", "verified", "blocked")
CAMPAIGN_DIR = Path("docs/campaigns")
TABLE_HEADER = "| # | Phase | Status | Verify command | Commit |"
TABLE_RULE = "|---|-------|--------|----------------|--------|"


class CampaignError(RuntimeError):
    """Ledger is malformed, missing, or contradicted by git."""


@dataclass
class Phase:
    index: int
    name: str
    status: str
    verify: str
    commit: str

    def row(self) -> str:
        return (
            f"| {self.index} | {self.name} | {self.status} | "
            f"`{self.verify}` | {self.commit or '—'} |"
        )


@dataclass
class Campaign:
    path: Path
    slug: str
    goal: str
    branch: str
    phases: list[Phase]
    handoff: str = ""

    @property
    def last_verified(self) -> Phase | None:
        done = [p for p in self.phases if p.status == "verified"]
        return done[-1] if done else None

    @property
    def next_phase(self) -> Phase | None:
        for phase in self.phases:
            if phase.status in ("pending", "in-progress"):
                return phase
        return None


def git(*args: str, check: bool = True) -> str:
    proc = subprocess.run(["git", *args], capture_output=True, text=True, check=False)
    if check and proc.returncode != 0:
        raise CampaignError(f"git {' '.join(args)} failed: {proc.stderr.strip()}")
    return proc.stdout.strip()


def repo_root() -> Path:
    return Path(git("rev-parse", "--show-toplevel"))


def commit_exists(sha: str) -> bool:
    if not sha or sha == "—":
        return False
    proc = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}^{{commit}}"],
        capture_output=True,
        check=False,
    )
    return proc.returncode == 0


def is_dirty() -> bool:
    return bool(git("status", "--porcelain"))


def ledger_path(slug: str) -> Path:
    return repo_root() / CAMPAIGN_DIR / f"{slug}.md"


# ---------------------------------------------------------------- parse / write


def parse(path: Path) -> Campaign:
    if not path.exists():
        raise CampaignError(f"no campaign ledger at {path}")
    text = path.read_text()
    lines = text.splitlines()

    def field(label: str) -> str:
        for line in lines:
            if line.startswith(f"**{label}:**"):
                return line.split(f"**{label}:**", 1)[1].strip()
        raise CampaignError(f"{path}: missing '**{label}:**' line")

    phases: list[Phase] = []
    in_table = False
    for line in lines:
        if line.strip().startswith("| # |"):
            in_table = True
            continue
        if in_table:
            if not line.strip().startswith("|"):
                in_table = False
                continue
            if set(line.strip()) <= set("|- "):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) != 5:
                raise CampaignError(f"{path}: phase row needs 5 columns, got {len(cells)}: {line}")
            idx, name, status, verify, commit = cells
            if status not in STATUSES:
                raise CampaignError(f"{path}: phase {idx} status {status!r} not one of {STATUSES}")
            phases.append(
                Phase(
                    index=int(idx),
                    name=name,
                    status=status,
                    verify=verify.strip("`"),
                    commit="" if commit in ("—", "-", "") else commit,
                )
            )
    if not phases:
        raise CampaignError(f"{path}: no phase rows found")

    handoff = ""
    if "## Handoff" in text:
        handoff = text.split("## Handoff", 1)[1].strip()

    return Campaign(
        path=path,
        slug=path.stem,
        goal=field("Goal"),
        branch=field("Branch"),
        phases=phases,
        handoff=handoff,
    )


def render(camp: Campaign) -> str:
    rows = "\n".join(p.row() for p in camp.phases)
    return (
        f"# Campaign: {camp.slug}\n\n"
        f"**Goal:** {camp.goal}\n"
        f"**Branch:** {camp.branch}\n\n"
        "A phase is `verified` only when `scripts/campaign.py verify` ran its\n"
        "command to a pass AND recorded the commit below. Never hand-edit a\n"
        "status to `verified`; `audit` will catch it.\n\n"
        "## Phases\n\n"
        f"{TABLE_HEADER}\n{TABLE_RULE}\n{rows}\n\n"
        "## Handoff\n\n"
        f"{camp.handoff or '_(none yet — written by `campaign.py handoff`)_'}\n"
    )


def save(camp: Campaign, message: str) -> None:
    camp.path.parent.mkdir(parents=True, exist_ok=True)
    camp.path.write_text(render(camp))
    rel = camp.path.relative_to(repo_root())
    git("add", str(rel))
    proc = subprocess.run(
        ["git", "commit", "-m", message, "--", str(rel)],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0 and "nothing to commit" not in proc.stdout:
        raise CampaignError(f"ledger commit failed: {proc.stdout}{proc.stderr}")


# ---------------------------------------------------------------- subcommands


def cmd_init(args: argparse.Namespace) -> int:
    path = ledger_path(args.slug)
    if path.exists() and not args.force:
        raise CampaignError(f"{path} exists; pass --force to overwrite")
    phases = []
    for i, spec in enumerate(args.phase, start=1):
        if "::" not in spec:
            raise CampaignError(f"--phase needs 'name::command', got {spec!r}")
        name, cmd = spec.split("::", 1)
        phases.append(Phase(i, name.strip(), "pending", cmd.strip(), ""))
    camp = Campaign(
        path=path,
        slug=args.slug,
        goal=args.goal,
        branch=git("branch", "--show-current"),
        phases=phases,
    )
    save(camp, f"chore(campaign): open ledger for {args.slug}")
    print(f"opened {path.relative_to(repo_root())} with {len(phases)} phases")
    return 0


def summary(camp: Campaign) -> str:
    verified = sum(1 for p in camp.phases if p.status == "verified")
    blocked = [p for p in camp.phases if p.status == "blocked"]
    last = camp.last_verified
    nxt = camp.next_phase
    dirty = git("status", "--porcelain")
    # `git worktree list` is "<path>  <sha> [<branch>]" — the path is field 0.
    worktrees = [line.split()[0] for line in git("worktree", "list").splitlines() if line.strip()]
    lines = [
        f"CAMPAIGN  {camp.slug} — {camp.goal}",
        f"PROGRESS  {verified}/{len(camp.phases)} phases verified"
        + (f", {len(blocked)} blocked" if blocked else ""),
        f"BRANCH    {git('branch', '--show-current')} (ledger says {camp.branch})",
        f"HEAD      {git('rev-parse', '--short', 'HEAD')} {git('log', '-1', '--pretty=%s')}",
        f"TREE      {'DIRTY — ' + str(len(dirty.splitlines())) + ' file(s)' if dirty else 'clean'}",
        f"WORKTREES {len(worktrees)}: {', '.join(Path(w).name for w in worktrees[:4])}",
        f"LAST OK   {('phase ' + str(last.index) + ' ' + last.name + ' @ ' + last.commit) if last else 'none'}",
        f"NEXT      {('phase ' + str(nxt.index) + ' ' + nxt.name) if nxt else 'campaign complete'}",
        f"VERIFY    {nxt.verify if nxt else '—'}",
        f"BLOCKED   {', '.join(p.name for p in blocked) if blocked else 'nothing'}",
    ]
    return "\n".join(lines)


def cmd_status(args: argparse.Namespace) -> int:
    print(summary(parse(ledger_path(args.slug))))
    return 0


def run_verify_command(cmd: str) -> tuple[bool, str]:
    proc = subprocess.run(
        cmd,
        shell=True,
        capture_output=True,
        text=True,
        check=False,
        cwd=repo_root(),
    )
    tail = (proc.stdout + proc.stderr).strip().splitlines()
    return proc.returncode == 0, "\n".join(tail[-15:])


def cmd_verify(args: argparse.Namespace) -> int:
    camp = parse(ledger_path(args.slug))
    phase = next((p for p in camp.phases if p.index == args.number), None)
    if phase is None:
        raise CampaignError(f"no phase {args.number} in {camp.slug}")

    ok, tail = run_verify_command(phase.verify)
    print(tail)
    if not ok:
        phase.status = "in-progress"
        save(camp, f"chore(campaign): phase {phase.index} still failing")
        print(f"\nNOT DONE — phase {phase.index} command failed: {phase.verify}")
        return 1

    if is_dirty():
        print(
            f"\nNOT DONE — phase {phase.index} passed but the tree is dirty.\n"
            "A verified phase must be committed. Commit the work, then re-run."
        )
        return 1

    sha = git("rev-parse", "--short", "HEAD")
    if not commit_exists(sha):
        raise CampaignError(f"HEAD {sha} does not resolve to a commit")
    phase.status = "verified"
    phase.commit = sha
    save(
        camp,
        f"chore(campaign): verify phase {phase.index} ({phase.name}) @ {sha}",
    )
    print(f"\nVERIFIED phase {phase.index} ({phase.name}) @ {sha}")
    return 0


def cmd_block(args: argparse.Namespace) -> int:
    camp = parse(ledger_path(args.slug))
    phase = next((p for p in camp.phases if p.index == args.number), None)
    if phase is None:
        raise CampaignError(f"no phase {args.number}")
    phase.status = "blocked"
    save(camp, f"chore(campaign): block phase {phase.index} — {args.reason}")
    print(f"blocked phase {phase.index}: {args.reason}")
    return 0


def cmd_audit(args: argparse.Namespace) -> int:
    camp = parse(ledger_path(args.slug))
    liars = [p for p in camp.phases if p.status == "verified" and not commit_exists(p.commit)]
    if liars:
        print("NOT DONE — ledger claims verified without a real commit:")
        for p in liars:
            print(f"  phase {p.index} {p.name}: commit {p.commit or '(none)'}")
        return 1
    print(f"audit clean — {len(camp.phases)} phases, every verified claim has a commit")
    return 0


def cmd_resume(args: argparse.Namespace) -> int:
    camp = parse(ledger_path(args.slug))
    print(summary(camp))
    print()

    rc = 0
    liars = [p for p in camp.phases if p.status == "verified" and not commit_exists(p.commit)]
    if liars:
        print(
            "LEDGER LIES — verified phases with no such commit: "
            + ", ".join(f"{p.index}:{p.commit or 'none'}" for p in liars)
        )
        rc = 1

    last = camp.last_verified
    if last:
        print(f"re-proving last verified phase {last.index}: {last.verify}")
        ok, tail = run_verify_command(last.verify)
        if not ok:
            print(tail)
            print(
                f"LEDGER LIES — phase {last.index} is marked verified but its "
                "command fails now. Treat it as in-progress."
            )
            rc = 1
        else:
            print(f"confirmed — phase {last.index} still passes")

    if is_dirty():
        print("\nUNCOMMITTED WIP — resolve before starting new work:")
        print(git("status", "--short"))
        rc = 1

    if rc:
        print("\nNOT DONE — fix the above before continuing the campaign.")
    return rc


def cmd_handoff(args: argparse.Namespace) -> int:
    camp = parse(ledger_path(args.slug))
    nxt = camp.next_phase
    branches = git("branch", "--format=%(refname:short) %(upstream:track)")
    worktrees = git("worktree", "list")
    procs = subprocess.run(
        "ps -eo pid,command | grep -E 'kitty|uvicorn|next|builder' | grep -v grep | head -8",
        shell=True,
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    camp.handoff = (
        f"_Written by `campaign.py handoff` at {git('rev-parse', '--short', 'HEAD')}._\n\n"
        f"**Single next action:** "
        f"{('phase ' + str(nxt.index) + ' — ' + nxt.name + ' (`' + nxt.verify + '`)') if nxt else 'none, campaign complete'}\n\n"
        "**Branches**\n\n```\n" + (branches or "(none)") + "\n```\n\n"
        "**Worktrees**\n\n```\n" + (worktrees or "(none)") + "\n```\n\n"
        "**Running processes**\n\n```\n" + (procs or "(none detected)") + "\n```\n"
    )
    save(camp, f"chore(campaign): handoff for {camp.slug}")
    print(f"handoff written to {camp.path.relative_to(repo_root())}")
    print(f"next action: {nxt.name if nxt else 'campaign complete'}")
    return 0


def cmd_list(_args: argparse.Namespace) -> int:
    root = repo_root() / CAMPAIGN_DIR
    if not root.exists():
        print("no campaigns yet")
        return 0
    for path in sorted(root.glob("*.md")):
        try:
            camp = parse(path)
        except CampaignError as exc:
            print(f"{path.stem}: MALFORMED — {exc}")
            continue
        verified = sum(1 for p in camp.phases if p.status == "verified")
        print(f"{camp.slug}: {verified}/{len(camp.phases)} verified — {camp.goal}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "campaign ledger").splitlines()[0])
    parser.add_argument("--slug", default=os.environ.get("CAMPAIGN_SLUG", "current"))
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_init = sub.add_parser("init", help="open a new campaign ledger")
    p_init.add_argument("--goal", required=True)
    p_init.add_argument("--phase", action="append", required=True, metavar="NAME::COMMAND")
    p_init.add_argument("--force", action="store_true")
    p_init.set_defaults(func=cmd_init)

    sub.add_parser("status", help="10-line where-we-are").set_defaults(func=cmd_status)
    sub.add_parser("resume", help="status + re-prove last verified + WIP check").set_defaults(
        func=cmd_resume
    )
    sub.add_parser("audit", help="flag verified claims with no commit").set_defaults(func=cmd_audit)
    sub.add_parser("handoff", help="write the pre-exit HANDOFF section").set_defaults(
        func=cmd_handoff
    )
    sub.add_parser("list", help="all campaigns").set_defaults(func=cmd_list)

    p_verify = sub.add_parser("verify", help="run a phase's command; mark verified")
    p_verify.add_argument("number", type=int)
    p_verify.set_defaults(func=cmd_verify)

    p_block = sub.add_parser("block", help="mark a phase blocked")
    p_block.add_argument("number", type=int)
    p_block.add_argument("reason")
    p_block.set_defaults(func=cmd_block)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except CampaignError as exc:
        print(f"NOT DONE — {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
