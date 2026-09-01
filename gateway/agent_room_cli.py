"""Local CLI for Kitty's canonical global agent room."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from gateway import agent_workspace
from gateway import db as kitty_db

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


def _with_receipt_state(row: Any) -> dict[str, Any]:
    result = dict(row)
    if result.get("acknowledged_at") is not None:
        result["receipt_state"] = "acknowledged"
    elif result.get("seen_at") is not None:
        result["receipt_state"] = "seen"
    else:
        result["receipt_state"] = "sent"
    return result


def _direct_inbox(
    participant_id: str, *, unread_only: bool = False, limit: int = 100
) -> list[dict[str, Any]]:
    """Return only messages explicitly addressed to one global participant."""
    participant_id = agent_workspace.validate_global_participant(participant_id)
    if not isinstance(unread_only, bool):
        raise agent_workspace.AgentWorkspaceError("unread_only must be a boolean")
    if isinstance(limit, bool) or limit <= 0 or limit > 500:
        raise agent_workspace.AgentWorkspaceError("limit must be between 1 and 500")
    agent_workspace.ensure_global_workspace()
    with kitty_db.connect(agent_workspace.WORKSPACE_DB_FILE) as conn:
        if participant_id == "jacob":
            joined = conn.execute(
                "SELECT created_at FROM agent_workspaces WHERE id = ?",
                (agent_workspace.GLOBAL_WORKSPACE_ID,),
            ).fetchone()
        else:
            joined = conn.execute(
                """
                SELECT created_at FROM agent_workspace_agents
                WHERE workspace_id = ? AND agent_id = ?
                """,
                (agent_workspace.GLOBAL_WORKSPACE_ID, participant_id),
            ).fetchone()
        if joined is None:
            raise agent_workspace.AgentWorkspaceError(
                f"unknown global participant {participant_id}"
            )
        rows = conn.execute(
            """
            SELECT m.*, r.seen_at, r.acknowledged_at
            FROM agent_workspace_messages AS m
            LEFT JOIN agent_workspace_message_receipts AS r
              ON r.message_id = m.id AND r.participant_id = ?
            WHERE m.workspace_id = ?
              AND m.sender_id <> ?
              AND m.created_at >= ?
              AND m.recipient_id = ?
              AND (? = 0 OR r.seen_at IS NULL)
            ORDER BY m.created_at DESC, m.id DESC
            LIMIT ?
            """,
            (
                participant_id,
                agent_workspace.GLOBAL_WORKSPACE_ID,
                participant_id,
                float(joined["created_at"]),
                participant_id,
                1 if unread_only else 0,
                limit,
            ),
        ).fetchall()
    return [_with_receipt_state(row) for row in reversed(rows)]


def _dispatch(args: argparse.Namespace) -> Any:
    if args.command == "ensure":
        return agent_workspace.ensure_global_workspace()
    if args.command == "status":
        return _status()
    if args.command == "recent":
        agent_workspace.ensure_global_workspace()
        return agent_workspace.list_messages(agent_workspace.GLOBAL_WORKSPACE_ID, limit=args.limit)
    if args.command == "inbox":
        if args.direct_only:
            return _direct_inbox(
                args.participant_id, unread_only=args.unread, limit=args.limit
            )
        return agent_workspace.list_inbox(
            args.participant_id, unread_only=args.unread, limit=args.limit
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
