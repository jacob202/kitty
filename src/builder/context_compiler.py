from __future__ import annotations

from pathlib import Path

from src.builder.contracts import BuilderBrief


def build_context_pack(
    project_root: str | Path,
    brief: BuilderBrief,
    *,
    max_chars_per_file: int = 4000,
) -> str:
    root = Path(project_root).expanduser().resolve()
    lines = [
        "# KittyBuilder Context Pack",
        "",
        "## Static Rules",
        "- Follow AGENTS.md and docs/LAYER0_CONTROL_PLANE.md authority order.",
        "- Optimize for effectiveness per token, not cheapest output.",
        "- Keep scope bounded to the compiled brief unless explicitly redirected.",
        "",
        "## Compiled Goal",
        brief.normalized_goal,
        "",
        "## Selected Context",
    ]

    for rel in brief.context_targets:
        path = (root / rel).resolve()
        if not _inside_project(path, root) or not path.is_file():
            lines.extend([f"### {rel}", "[missing or outside project]"])
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if len(text) > max_chars_per_file:
            text = text[:max_chars_per_file] + "\n[truncated]"
        lines.extend([f"### {rel}", "```text", text, "```"])

    if brief.next_agent_packet:
        lines.extend(
            [
                "",
                "## Next-Agent Packet",
                "```json",
                _packet_json(brief.next_agent_packet),
                "```",
            ]
        )

    lines.extend(["", "## Final Acceptance Checklist"])
    for item in brief.success_criteria or ["Compiled goal is satisfied."]:
        lines.append(f"- {item}")
    for command in brief.validation_commands:
        lines.append(f"- Run: `{command}`")
    return "\n".join(lines).strip() + "\n"


def _inside_project(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _packet_json(packet: dict[str, object]) -> str:
    import json

    return json.dumps(packet, indent=2, sort_keys=True)
