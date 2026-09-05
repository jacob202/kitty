"""Local CLI for Kitty's canonical global agent room."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from gateway import agent_coordination, agent_workspace

_MESSAGE_KINDS = ("prompt", "plan", "handoff", "review", "result", "status")


def _json_flag(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", dest="as_json")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kitty room")
    sub = parser.add_subparsers(dest="command", required=True)

    ensure = sub.add_parser("ensure")
    _json_flag(ensure)
    status = sub.add_parser("status")
    _json_flag(status)

    recent = sub.add_parser("recent")
    recent.add_argument("--limit", type=int, default=100)
    _json_flag(recent)

    inbox = sub.add_parser("inbox")
    inbox.add_argument("--as", dest="participant_id", required=True)
    inbox.add_argument("--unread", action="store_true")
    inbox.add_argument("--direct-only", action="store_true", dest="direct_only")
    inbox.add_argument("--limit", type=int, default=100)
    _json_flag(inbox)

    thread = sub.add_parser("thread")
    thread.add_argument("message_id")
    thread.add_argument("--limit", type=int, default=100)
    _json_flag(thread)

    post = sub.add_parser("post")
    post.add_argument("--as", dest="sender_id", required=True)
    post.add_argument("--to", dest="recipient_id")
    post.add_argument("--kind", choices=_MESSAGE_KINDS, default="status")
    post.add_argument("content")
    _json_flag(post)

    reply = sub.add_parser("reply")
    reply.add_argument("--as", dest="sender_id", required=True)
    reply.add_argument("--to", dest="recipient_id")
    reply.add_argument("--kind", choices=_MESSAGE_KINDS, default="status")
    reply.add_argument("message_id")
    reply.add_argument("content")
    _json_flag(reply)

    ack = sub.add_parser("ack")
    ack.add_argument("--as", dest="participant_id", required=True)
    ack.add_argument("message_id")
    _json_flag(ack)

    # Presence subcommands
    checkin = sub.add_parser("checkin")
    checkin.add_argument("--as", dest="participant_id", required=True)
    checkin.add_argument("--session-id", dest="session_id", required=True)
    checkin.add_argument("--runtime")
    checkin.add_argument("--role")
    checkin.add_argument("--lane", dest="lane_id")
    checkin.add_argument("--ref", dest="exact_ref")
    checkin.add_argument("--summary")
    checkin.add_argument("--status", dest="declared_status")
    _json_flag(checkin)

    heartbeat = sub.add_parser("heartbeat")
    heartbeat.add_argument("--as", dest="participant_id", required=True)
    heartbeat.add_argument("--session-id", dest="session_id", required=True)
    _json_flag(heartbeat)

    checkout = sub.add_parser("checkout")
    checkout.add_argument("--as", dest="participant_id", required=True)
    checkout.add_argument("--session-id", dest="session_id", required=True)
    _json_flag(checkout)

    presence = sub.add_parser("presence")
    presence.add_argument("--as", dest="participant_id")
    presence.add_argument("--limit", type=int, default=100)
    _json_flag(presence)

    return parser


def _emit(value: Any, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(value, sort_keys=True))
        return
    if isinstance(value, list):
        for item in value:
            if isinstance(item, dict):
                print(f"{item.get('id', '-')}: {item.get('sender_id', '-')}: {item.get('content', '')}")
            else:
                print(item)
        return
    if isinstance(value, dict):
        print(json.dumps(value, sort_keys=True))
        return
    print(value)


def _status() -> dict[str, Any]:
    room = agent_workspace.ensure_global_workspace()
    return {
        "id": room["id"],
        "name": room["name"],
        "status": room["status"],
        "participants": [agent["id"] for agent in room["agents"]],
        "message_count": len(room["messages"]),
    }


def _renew_coordination_claim_if_active(session_id: str) -> None:
    db_path = agent_coordination.default_db_path()
    if not db_path.exists():
        return
    active = agent_coordination.list_claims(active_only=True, db_path=db_path)
    if not any(claim["session_id"] == session_id for claim in active):
        return
    try:
        agent_coordination.renew(session_id, db_path=db_path)
    except agent_coordination.CoordinationClaimError as exc:
        raise AgentRoomCliError(f"coordination heartbeat renewal failed: {exc}") from exc


def _dispatch(args: argparse.Namespace) -> Any:
    if args.command == "ensure":
        return agent_workspace.ensure_global_workspace()
    if args.command == "status":
        return _status()
    if args.command == "recent":
        agent_workspace.ensure_global_workspace()
        return agent_workspace.list_messages(agent_workspace.GLOBAL_WORKSPACE_ID, limit=args.limit)
    if args.command == "inbox":
        return agent_workspace.list_inbox(
            args.participant_id,
            unread_only=args.unread,
            direct_only=args.direct_only,
            limit=args.limit,
        )
    if args.command == "thread":
        return agent_workspace.list_thread(args.message_id, limit=args.limit)
    if args.command == "post":
        return agent_workspace.post_global_message(
            sender_id=args.sender_id,
            recipient_id=args.recipient_id,
            content=args.content,
            message_kind=args.kind,
        )
    if args.command == "reply":
        return agent_workspace.post_global_message(
            sender_id=args.sender_id,
            recipient_id=args.recipient_id,
            content=args.content,
            message_kind=args.kind,
            parent_message_id=args.message_id,
        )
    if args.command == "ack":
        return agent_workspace.record_receipt(
            args.message_id, args.participant_id, "acknowledged"
        )
    if args.command == "checkin":
        return agent_workspace.check_in(
            participant_id=args.participant_id,
            session_id=args.session_id,
            runtime=args.runtime,
            role=args.role,
            lane_id=args.lane_id,
            exact_ref=args.exact_ref,
            summary=args.summary,
            declared_status=args.declared_status,
        )
    if args.command == "heartbeat":
        result = agent_workspace.heartbeat(args.session_id, args.participant_id)
        _renew_coordination_claim_if_active(args.session_id)
        return result
    if args.command == "checkout":
        return agent_workspace.checkout(
            args.session_id, args.participant_id
        )
    if args.command == "presence":
        return agent_workspace.list_presence(
            participant_id=args.participant_id,
            limit=args.limit,
        )
    raise AgentRoomCliError(f"unsupported command {args.command}")


class AgentRoomCliError(RuntimeError):
    """Raised for an invalid CLI dispatch."""


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        result = _dispatch(args)
    except (agent_workspace.AgentWorkspaceError, AgentRoomCliError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    _emit(result, as_json=args.as_json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
