"""Canonical capability inventory for Kitty's visible product surface."""

from __future__ import annotations

import collections
import json
from dataclasses import dataclass
from pathlib import Path
import threading


_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_CRUSH_CONFIG = _PROJECT_ROOT / "crush.json"


@dataclass(frozen=True)
class CommandCapability:
    command: str
    description: str
    tier: str = "core"
    status: str = "keep"
    visible_in_help: bool = True
    visible_in_palette: bool = True
    keywords: tuple[str, ...] = ()
    routing_tags: tuple[str, ...] = ()


_COMMANDS: tuple[CommandCapability, ...] = (
    CommandCapability("/brief", "morning brief, where you left off", keywords=("brief", "morning", "summary"), routing_tags=("brief", "morning", "summary")),
    CommandCapability("/stuck [task]", "ADHD rescue: one next physical step", keywords=("stuck", "focus", "rescue", "improve"), routing_tags=("stuck", "focus", "bug", "overwhelmed")),
    CommandCapability("/bench [mode|off]", "set work mode (sansui, ridgeline, heathkit, or custom)", keywords=("bench", "mode", "hardware"), routing_tags=("mode", "hardware", "project")),
    CommandCapability("/capture <thought>", "quick brain dump", keywords=("capture", "note", "thought", "save"), routing_tags=("capture", "note", "thought")),
    CommandCapability("/review", "show captures and saved facts", keywords=("review", "memory", "saved"), routing_tags=("review", "saved", "memory")),
    CommandCapability("/remember <fact>", "save a persistent fact", keywords=("remember", "memory", "fact"), routing_tags=("remember", "fact", "memory")),
    CommandCapability("/deepsearch [query]", "web search + synthesis", keywords=("deepsearch", "research", "web", "investigate"), routing_tags=("research", "investigate", "search", "web")),
    CommandCapability("/screen [question]", "screenshot + vision analysis", keywords=("screen", "screenshot", "vision"), routing_tags=("screen", "screenshot", "vision")),
    CommandCapability("/repair <photo> [context]", "repair photo analysis", keywords=("repair", "photo", "hardware", "diagnose"), routing_tags=("repair", "diagnose", "photo", "hardware")),
    CommandCapability("/image <photo> [question]", "ask a vision question about an image", keywords=("image", "photo", "vision"), routing_tags=("image", "photo", "vision")),
    CommandCapability("/status", "show models, tools, and capability status", keywords=("status", "health", "capabilities"), routing_tags=("status", "health", "capabilities")),
    CommandCapability("/clear", "clear conversation history", keywords=("clear", "history"), routing_tags=("clear", "history", "reset")),
    CommandCapability("/skills", "list all registered skills", keywords=("skills", "discover", "workflow"), routing_tags=("skills", "discover", "workflow")),
    CommandCapability("/skill <name>", "load a skill into context (max 3)", keywords=("skill", "load", "workflow"), routing_tags=("skill", "load", "workflow")),
    CommandCapability("/skill-unload <name>", "remove a loaded skill from context", keywords=("skill", "unload"), routing_tags=("skill", "unload")),
    CommandCapability("/skill-clear", "unload all loaded skills", keywords=("skill", "clear"), routing_tags=("skill", "clear")),
    CommandCapability("/skill-loaded", "show which skills are currently loaded", keywords=("skill", "loaded"), routing_tags=("skill", "loaded")),
    CommandCapability("/help", "show the core command set", keywords=("help", "commands"), routing_tags=("help", "commands")),
    CommandCapability("/prep", "run prescriber prep", tier="internal", status="hide", visible_in_help=False, visible_in_palette=False, keywords=("prep",), routing_tags=("prep",)),
    CommandCapability("/optic [question]", "capture the screen and OCR or inspect it", tier="beta", status="hide", visible_in_help=False, keywords=("optic", "ocr", "screen"), routing_tags=("optic", "ocr", "screen")),
    CommandCapability("/ocr [path]", "extract text from a screenshot or image", tier="beta", status="hide", visible_in_help=False, keywords=("ocr", "text"), routing_tags=("ocr", "text")),
    CommandCapability("/scrape <url>", "fetch and analyze a public webpage", tier="beta", status="hide", visible_in_help=False, keywords=("scrape", "web", "research"), routing_tags=("scrape", "web", "research")),
    CommandCapability("/cal [days]", "list upcoming calendar events", tier="beta", status="hide", visible_in_help=False, keywords=("calendar", "schedule"), routing_tags=("calendar", "schedule")),
    CommandCapability("/watch [on|off|30]", "continuous screen watcher", tier="beta", status="hide", visible_in_help=False, keywords=("watch", "screen"), routing_tags=("watch", "screen")),
    CommandCapability("/council <topic>", "dynamic expert panel for a topic", tier="beta", status="hide", visible_in_help=False, keywords=("council", "debate", "experts"), routing_tags=("council", "experts", "debate")),
)

_MCP_POLICY = {
    "filesystem": {
        "tier": "core",
        "status": "keep",
        "reason": "Required for local repo and file-aware workflows.",
    },
    "memory": {
        "tier": "beta",
        "status": "keep",
        "reason": "Kept as part of Kitty's current memory layer, but still not promoted as a broad UI capability.",
    },
    "sequential-thinking": {
        "tier": "beta",
        "status": "investigate",
        "reason": "Useful for agent environments, but not clearly exposed as Kitty-native capability.",
    },
}

_VALID_TIERS = frozenset({"core", "beta", "internal", "disabled"})
_VALID_STATUSES = frozenset({"keep", "hide", "remove", "investigate"})
_VALID_OUTCOMES = frozenset({"suggested", "selected", "auto-invoked", "succeeded", "failed", "canceled", "abandoned"})
_invocation_lock = threading.Lock()
_invocations: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)


def _serialize_command_capability(command: CommandCapability) -> dict[str, object]:
    return {
        "command": command.command,
        "description": command.description,
        "tier": command.tier,
        "status": command.status,
        "visible_in_help": command.visible_in_help,
        "visible_in_palette": command.visible_in_palette,
        "keywords": list(command.keywords),
        "routing_tags": list(command.routing_tags),
    }


def command_names() -> list[str]:
    return [command.command.split()[0] for command in _COMMANDS]


def all_command_capabilities() -> list[CommandCapability]:
    return list(_COMMANDS)


def visible_help_commands() -> list[CommandCapability]:
    return [command for command in _COMMANDS if command.visible_in_help]


def find_command_capability(command_name: str) -> CommandCapability | None:
    leading = command_name.strip().split()[0] if command_name.strip() else ""
    if not leading:
        return None
    for command in _COMMANDS:
        if command.command.split()[0] == leading:
            return command
    return None


def command_capability_snapshot() -> list[dict[str, object]]:
    return [_serialize_command_capability(command) for command in _COMMANDS]


def record_invocation(command: str, *, outcome: str) -> None:
    if outcome not in _VALID_OUTCOMES:
        raise ValueError(f"outcome must be one of {sorted(_VALID_OUTCOMES)}, got {outcome!r}")
    with _invocation_lock:
        _invocations[command][outcome] += 1


def invocation_stats(command: str | None = None) -> dict:
    with _invocation_lock:
        if command is not None:
            return dict(_invocations.get(command, {}))
        return {cmd: dict(counts) for cmd, counts in _invocations.items()}


def reset_invocation_stats() -> None:
    with _invocation_lock:
        _invocations.clear()


def command_palette_suggestions(query: str, *, limit: int = 3) -> list[dict[str, str]]:
    query_tokens = [token for token in query.lower().split() if token]
    if not query_tokens:
        return [
            {
                "command": command.command,
                "description": command.description,
                "tier": command.tier,
                "status": command.status,
            }
            for command in _COMMANDS
            if command.visible_in_palette and command.tier == "core"
        ][:limit]

    ranked: list[tuple[int, CommandCapability]] = []
    for command in _COMMANDS:
        if not command.visible_in_palette:
            continue
        haystack = " ".join((command.command, command.description, *command.keywords, *command.routing_tags)).lower()
        score = sum(1 for token in query_tokens if token in haystack)
        if score:
            ranked.append((score, command))

    ranked.sort(key=lambda item: (-item[0], item[1].tier != "core", item[1].command))
    return [
        {
            "command": command.command,
            "description": command.description,
            "tier": command.tier,
            "status": command.status,
        }
        for _, command in ranked[:limit]
    ]


def repo_mcp_inventory() -> dict[str, dict[str, object]]:
    configured = {}
    if _CRUSH_CONFIG.exists():
        configured = json.loads(_CRUSH_CONFIG.read_text(encoding="utf-8")).get("mcp", {})

    inventory: dict[str, dict[str, object]] = {}
    for name, policy in _MCP_POLICY.items():
        inventory[name] = {
            "configured": name in configured,
            **policy,
        }
    return inventory


def capability_snapshot(*, enable_experimental_swarm: bool, enable_internal_api: bool = False) -> dict[str, object]:
    visible = visible_help_commands()
    all_commands = command_capability_snapshot()
    return {
        "commands": {
            "total_count": len(_COMMANDS),
            "visible_help_count": len(visible),
            "core_count": sum(1 for command in _COMMANDS if command.tier == "core"),
            "beta_count": sum(1 for command in _COMMANDS if command.tier == "beta"),
            "internal_count": sum(1 for command in _COMMANDS if command.tier == "internal"),
            "visible": [_serialize_command_capability(command) for command in visible],
            "all": all_commands,
        },
        "api": {
            "swarm": {
                "path_prefix": "/api/swarm",
                "tier": "beta" if enable_experimental_swarm else "disabled",
                "enabled": enable_experimental_swarm,
                "reason": "Hidden by default until the backend is dependable.",
            },
            "scorecard": {
                "path": "/api/eval/scorecard",
                "tier": "internal",
                "enabled": enable_internal_api,
                "reason": "Internal diagnostics surface, hidden by default in web mode.",
            },
            "api_health": {
                "path": "/api/health",
                "tier": "internal",
                "enabled": enable_internal_api,
                "reason": "Detailed health payload kept behind the internal API flag.",
            },
            "settings_update": {
                "path": "/api/settings/update",
                "tier": "internal",
                "enabled": enable_internal_api,
                "reason": "Settings mutation is internal-only and hidden by default in web mode.",
            },
        },
        "mcp": repo_mcp_inventory(),
    }
