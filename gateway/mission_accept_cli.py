"""Local operator command for recording running-product Mission acceptance.

`mission_runtime.record_running_product_acceptance` is deliberately not exposed
over HTTP: reviewer identity, runtime checkout identity, data-root identity and
artifact provenance are derived locally rather than asserted by a product
client. This module is the operator's way in.

Three steps, in order:

    kitty accept status                      what is waiting, and what blocks it
    kitty accept template <mission-id> -o F  an evidence file to fill in
    kitty accept record <mission-id> -e F    the verdict, bound to the candidate
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from gateway import memory_mission, mission_runtime

_AWAITING_STATUSES = ("VERIFYING", "EXECUTING", "REPAIRING")

_STATE_LABELS = {
    "desktop": "Desktop width",
    "iphone_class": "iPhone-class width",
    "happy": "The journey when nothing goes wrong",
    "degraded": "The journey when something fails",
    "reload": "Reload mid-journey",
    "recovery": "Recovery after an interruption",
}


def _awaiting_missions() -> list[dict[str, Any]]:
    missions = memory_mission.list_missions(db_path=memory_mission.MISSION_DB_FILE)
    return [
        mission
        for mission in missions
        if mission["status"] in _AWAITING_STATUSES
        and mission["acceptance"]["state"] == "unreviewed"
    ]


# A blocker with no next command is a task handed back. Each row is
# (marker in the exact reason, what it means, the one command that clears it).
_PLAIN_BLOCKERS = (
    (
        "GATEWAY_SECRET",
        "Kitty is not running, or this shell cannot reach it.",
        "./kitty up",
    ),
    (
        "Gateway runtime identity is unavailable",
        "Kitty's server is not running.",
        "./kitty up",
    ),
    (
        "expected reviewed SHA",
        "Kitty is running a different version than the one that was reviewed.",
        "git checkout <built from>, then ./kitty down && ./kitty up && make ui-build",
    ),
    (
        "UI is not serving",
        "The screen you would check was built from a different version.",
        "make ui-build",
    ),
    (
        "runtime checkout is not clean",
        "The code folder has uncommitted edits, so the version cannot be pinned.",
        "git status, then commit or stash what is there",
    ),
    (
        "does not match operator data root",
        "Kitty is running against different data than this command sees.",
        "run this command from the same folder Kitty is running from",
    ),
    (
        "no complete Builder task binding",
        "This job was never handed to the worker, so there is no result to accept.",
        None,
    ),
    (
        "has no independently reviewed ready result",
        "The worker finished, but nothing has reviewed the result yet.",
        None,
    ),
)


def _plain(blocker: str) -> tuple[str, str | None]:
    """Say what is missing, and the one command that clears it, when there is one."""
    for needle, sentence, fix in _PLAIN_BLOCKERS:
        if needle in blocker:
            return sentence, fix
    return blocker, None


def _cmd_status(args: argparse.Namespace) -> int:
    missions = _awaiting_missions()
    if args.mission_id:
        missions = [m for m in missions if m["mission_id"] == args.mission_id]
        if not missions:
            print(f"No job {args.mission_id!r} is waiting for acceptance.")
            return 1
    reports = [mission_runtime.acceptance_readiness(mission) for mission in missions]
    if args.json:
        print(json.dumps({"awaiting_acceptance": reports}, indent=2, sort_keys=True))
        return 0
    if not reports:
        print("Nothing is waiting for acceptance.")
        return 0
    for report in reports:
        print(f"{report['mission_id']}")
        print(f"  what it was for : {report['objective']}")
        print(f"  state           : {report['status']}")
        print(f"  result          : {report['candidate_ref'] or 'not bound yet'}")
        if report["ready"]:
            print("  ready to accept : yes")
            print(f"  built from      : {report['review_sha']}")
        else:
            sentence, fix = _plain(report["blocker"])
            print("  ready to accept : no")
            print(f"  what is missing : {sentence}")
            if fix:
                print(f"  what to do      : {fix}")
            if sentence != report["blocker"]:
                print(f"  exact reason    : {report['blocker']}")
        print()
    return 0


def _template(mission: dict[str, Any]) -> dict[str, Any]:
    candidate = mission.get("candidate") or {}
    return {
        "mission_id": mission["mission_id"],
        "candidate_ref": candidate.get("ref"),
        "candidate_digest": candidate.get("digest"),
        "steps": ["describe each step you actually performed, in order"],
        "unmet_gates": [],
        **{
            key: {"state": "unverified", "evidence": f"how you checked: {_STATE_LABELS.get(key, key)}"}
            for key in mission_runtime.REQUIRED_RUNNING_STATES
        },
    }


def _cmd_template(args: argparse.Namespace) -> int:
    mission = memory_mission.get_mission(
        args.mission_id, db_path=memory_mission.MISSION_DB_FILE
    )
    payload = _template(mission)
    text = json.dumps(payload, indent=2, sort_keys=True)
    if args.out:
        Path(args.out).write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.out}. Fill in every state, then run:")
        print(f"  kitty accept record {args.mission_id} --evidence-file {args.out}")
    else:
        print(text)
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    mission = memory_mission.get_mission(
        args.mission_id, db_path=memory_mission.MISSION_DB_FILE
    )
    candidate = mission.get("candidate") or {}
    try:
        evidence = json.loads(Path(args.evidence_file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"Cannot read the evidence file: {exc}", file=sys.stderr)
        return 2
    if not isinstance(evidence, dict):
        print("The evidence file must contain one JSON object.", file=sys.stderr)
        return 2
    # The template stamps the binding it was generated against. The Mission's
    # own candidate is still the authority, but a file written against a
    # superseded candidate must be refused rather than silently re-pointed:
    # otherwise an old fully-passing evidence file accepts a replacement
    # candidate that was never exercised.
    stamped_mission = evidence.pop("mission_id", None)
    stamped_ref = evidence.pop("candidate_ref", None)
    stamped_digest = evidence.pop("candidate_digest", None)
    live_ref = candidate.get("ref") or ""
    live_digest = candidate.get("digest") or ""
    stale: list[str] = []
    if stamped_mission is not None and stamped_mission != args.mission_id:
        stale.append(f"job {stamped_mission!r}, not {args.mission_id!r}")
    if stamped_ref is not None and stamped_ref != live_ref:
        stale.append(f"result {stamped_ref!r}, now {live_ref!r}")
    if stamped_digest is not None and stamped_digest != live_digest:
        stale.append("a different version of that result")
    if stale:
        print(
            "Refused — this evidence file describes " + "; ".join(stale) + ".",
            file=sys.stderr,
        )
        print(
            "  what to do: the job produced a new result while you were filling "
            "this in. Run `kitty accept template` again and redo the checks "
            "against the current result.",
            file=sys.stderr,
        )
        return 1
    try:
        accepted = mission_runtime.record_running_product_acceptance(
            args.mission_id,
            candidate_ref=candidate.get("ref") or "",
            candidate_digest=candidate.get("digest") or "",
            verdict=args.verdict,
            evidence=evidence,
        )
    except mission_runtime.ResultCandidateUnavailable as exc:
        sentence, fix = _plain(str(exc))
        print(f"Refused — {sentence}", file=sys.stderr)
        if fix:
            print(f"  what to do: {fix}", file=sys.stderr)
        print(f"  exact reason: {exc}", file=sys.stderr)
        return 1
    except memory_mission.MissionError as exc:
        print(f"Refused — {exc}", file=sys.stderr)
        return 1
    print(f"Recorded {args.verdict} for {args.mission_id}.")
    print(f"  job state : {accepted['status']}")
    print(f"  reviewer  : {accepted['acceptance']['reviewer_id']}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="kitty accept",
        description="Record acceptance of a finished job against the running product.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    status = subparsers.add_parser("status", help="what is waiting, and what blocks it")
    status.add_argument("mission_id", nargs="?")
    status.add_argument("--json", action="store_true")
    status.set_defaults(func=_cmd_status)

    template = subparsers.add_parser("template", help="write an evidence file to fill in")
    template.add_argument("mission_id")
    template.add_argument("-o", "--out")
    template.set_defaults(func=_cmd_template)

    record = subparsers.add_parser("record", help="record the verdict")
    record.add_argument("mission_id")
    record.add_argument("-e", "--evidence-file", required=True)
    record.add_argument(
        "--verdict", choices=["accepted", "rejected"], default="accepted"
    )
    record.set_defaults(func=_cmd_record)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return int(args.func(args))
    except memory_mission.MissionNotFound as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
