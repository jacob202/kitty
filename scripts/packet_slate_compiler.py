#!/usr/bin/env python3
"""Compile a structured packet slate into a Builder manifest and packet docs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

PACKET_KEYS = {"id", "title", "objective", "depends_on", "acceptance_criteria", "allowed_paths", "policy", "validation_commands"}


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
        acceptance = "\n".join(f"- {item}" for item in packet["acceptance_criteria"])
        commands = "\n".join(f"- `{item}`" for item in packet["validation_commands"])
        if lane == "builder":
            owner = "builder"
            owner_line = "**Free or paid:** free\n"
        elif lane == "held":
            owner = "builder (held)"
            owner_line = "**Builder manifest:** held\n"
        else:
            owner = "interactive"
            owner_line = "**Builder manifest:** none\n"
        if lane == "builder":
            boundary = "Backend-only packet. Frontend visibility/actionability is owned by its manifest-less interactive companion.\n\n"
        elif lane == "held":
            reason = entry.get("hold_reason") or "Release condition not yet satisfied."
            boundary = f"Backend packet, intentionally held out of the Builder manifest. Hold reason: {reason}\n\n"
        else:
            boundary = "Interactive/UI packet. It is intentionally omitted from the Builder manifest and must prove its frontend gates in the interactive lane.\n\n"
        document = (
            f"# {packet['id']} — {packet['title']}\n\n"
            f"**Initiative:** `{source['initiative_id']}`\n"
            f"**Owner:** {owner}\n"
            f"{owner_line}"
            f"**Base:** `origin/main` `{source['base_sha']}`\n\n"
            "## Outcome boundary\n"
            f"{boundary}"
            f"## Current finding\n{entry['finding']}\n\n"
            f"## Objective\n{packet['objective']}\n\n"
            f"## Acceptance\n{acceptance}\n\n"
            f"## Verification\n{commands}\n\n"
            "Existing green tests are only a baseline; the worker must add a regression for the missing behavior before production edits.\n\n"
            f"## Stop condition\n{entry['stop']}\n\n"
            f"## Recovery\n{entry['recovery']}\n"
        )
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
