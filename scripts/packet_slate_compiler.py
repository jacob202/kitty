#!/usr/bin/env python3
"""Compile a structured packet slate into a Builder manifest and packet docs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PACKET_KEYS = {
    "id", "title", "objective", "depends_on", "acceptance_criteria",
    "allowed_paths", "policy", "validation_commands",
}


def _validate_packet(packet: dict[str, object], *, lane: str) -> None:
    unknown = set(packet) - PACKET_KEYS
    if unknown:
        raise SystemExit(f"unknown packet manifest keys: {sorted(unknown)}")
    policy = packet.get("policy") or {}
    if isinstance(policy, dict) and policy.get("routing"):
        raise SystemExit("policy.routing is forbidden for free Builder slates")
    if lane == "builder":
        for command in packet.get("validation_commands", []):
            if isinstance(command, str) and ("npx " in command or "npm " in command):
                raise SystemExit("Node validation commands are not Builder-runnable")


def _numbered(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


def _bullets(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _commands(items: list[str]) -> str:
    return "\n".join(f"  - `{item}`" for item in items)


def _doc_for_entry(source: dict, entry: dict, packet: dict, lane: str) -> str:
    if lane == "builder":
        owner = "builder"
        owner_line = "**Free or paid:** free\n"
        manifest_note = "Backend-only packet. Its visible UI/actionability is owned by a manifest-less interactive companion."
    elif lane == "held":
        owner = "builder (held)"
        owner_line = "**Builder manifest:** held\n"
        reason = entry.get("hold_reason") or "Release condition not yet satisfied."
        manifest_note = f"Backend packet intentionally held out of Builder. Hold reason: {reason}"
    else:
        interactive_hold = entry.get("hold_reason")
        owner = "interactive (held)" if interactive_hold else "interactive"
        owner_line = "**Builder manifest:** none\n"
        manifest_note = (
            f"Interactive/UI packet intentionally held out of execution. Hold reason: {interactive_hold}"
            if interactive_hold
            else "Interactive/UI packet intentionally omitted from Builder; frontend gates run only in the interactive lane."
        )

    depends_on = packet.get("depends_on") or []
    dependencies = ", ".join(f"`{item}`" for item in depends_on) if depends_on else "none"
    outcome = entry.get("outcome") or (
        "The bounded capability in this packet is implemented and proven without creating a parallel system."
        if lane != "interactive"
        else "Jacob can use this capability from the running Kitty UI without falling back to a hidden backend route."
    )
    plan = entry.get("plan") or [
        "Add or update the narrow regression that proves the current finding.",
        "Implement the objective strictly inside the declared allowed-path fence.",
        "Run the packet gates and inspect the final diff for scope drift.",
    ]
    not_in_scope = entry.get("not_in_scope") or [
        "Work outside the declared allowed paths or beyond the stop condition.",
        "A parallel queue, state machine, registry, provider path, or persistence layer.",
        "Push, PR, merge, paid spend, secrets, or direct edits under data/ from the packet worker.",
    ]
    commands = list(packet.get("validation_commands") or [])

    if lane == "interactive":
        if entry.get("hold_reason"):
            tier1 = "Not run while held. After the hold clears, run:\n" + _commands(commands)
        else:
            tier1 = "Interactive validation commands:\n" + _commands(commands)
        tier2 = entry.get("tier2") or (
            "Run a targeted Playwright smoke under `gateway/kitty-chat/tests/smoke/` at desktop and iPhone-14 widths; "
            "the smoke must exercise the visible outcome and its degraded/error state."
        )
        tier3 = entry.get("tier3") or (
            "An independent reviewer exercises the running product, records Product Acceptance, and verifies the primary action is visible, tappable, truthful, and not obscured."
        )
    elif lane == "held":
        tier1 = "Not run while held. After the hold clears, run:\n" + _commands(commands)
        tier2 = entry.get("tier2") or "Not applicable until the hold clears; the eventual interactive companion owns browser smoke proof."
        tier3 = entry.get("tier3") or "Not applicable until the hold clears and the user-facing companion is ready for independent Product Acceptance."
    else:
        tier1 = "Builder-runnable commands:\n" + _commands(commands)
        tier2 = entry.get("tier2") or "Not applicable to this backend-only half; its manifest-less interactive companion owns the running-app Playwright smoke."
        tier3 = entry.get("tier3") or "Not applicable to this backend-only half; independent Product Acceptance is required on the user-facing companion before the door is considered finished."

    acceptance = _bullets(list(packet["acceptance_criteria"]))
    return (
        f"# {packet['id']} — {packet['title']}\n\n"
        f"**Initiative:** `{source['initiative_id']}`\n"
        f"**Owner:** {owner}\n"
        f"{owner_line}"
        f"**Base:** `origin/main` `{source['base_sha']}`\n"
        f"**Dependencies:** {dependencies}\n\n"
        f"{manifest_note}\n\n"
        "## What Jacob can do after this\n"
        f"{outcome}\n\n"
        "## Why this is the next thing\n"
        f"{entry['finding']}\n\n"
        "## Plan\n"
        f"{_numbered(list(plan))}\n\n"
        "## Not in scope\n"
        f"{_bullets(list(not_in_scope))}\n\n"
        "## Objective\n"
        f"{packet['objective']}\n\n"
        "## Acceptance criteria\n"
        f"{acceptance}\n\n"
        "## Verification\n"
        f"**Tier 1 — mechanical.** {tier1}\n\n"
        f"**Tier 2 — running app.** {tier2}\n\n"
        f"**Tier 3 — product acceptance.** {tier3}\n\n"
        "Existing green tests are only a baseline; implementation work must add or update a regression for the missing behavior before production edits.\n\n"
        "## Stop condition\n"
        f"{entry['stop']}\n\n"
        "## Recovery\n"
        f"{entry['recovery']}\n"
    )


def compile_slate(source_path: Path, manifest_out: Path, packet_dir: Path) -> None:
    source = json.loads(source_path.read_text(encoding="utf-8"))
    packet_dir.mkdir(parents=True, exist_ok=True)
    manifest_packets: list[dict[str, object]] = []

    for entry in source["packets"]:
        lane = entry.get("lane", "builder")
        if lane not in {"builder", "interactive", "held"}:
            raise SystemExit(f"unknown packet lane: {lane!r}")
        packet = dict(entry["manifest"])
        _validate_packet(packet, lane="builder" if lane == "held" else lane)
        if lane == "builder":
            manifest_packets.append(packet)
        document = _doc_for_entry(source, entry, packet, lane)
        (packet_dir / f"{packet['id']}.md").write_text(document, encoding="utf-8")

    manifest = {
        "manifest_version": source["manifest_version"],
        "initiative_id": source["initiative_id"],
        "title": source["title"],
        "description": source["description"],
        "packets": manifest_packets,
    }
    manifest_out.parent.mkdir(parents=True, exist_ok=True)
    manifest_out.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--manifest-out", required=True, type=Path)
    parser.add_argument("--packet-dir", required=True, type=Path)
    args = parser.parse_args()
    compile_slate(args.source, args.manifest_out, args.packet_dir)


if __name__ == "__main__":
    main()
