# KH-GAR-02 — bound what the agent room hands back

**Initiative:** kitty-hardening-v1
**Owner:** builder
**Depends on:** none
**Free or paid:** free

## What Jacob can do after this

Have an agent orient itself in the room in one call, instead of that call being
the one it cannot afford to make.

## Why this is the next thing

Measured on 2026-09-16, in this room:

- `room_status` returned **857,243 characters across 17,743 lines**
- `room_inbox` returned **111,369 characters**

Both exceeded what the calling agent could read and had to be spilled to disk and
grepped. The call that exists so an agent can find out where it stands is the
most expensive call it can make, and it gets more expensive every day the room is
used. An agent that follows the documented startup procedure pays that cost
before it has done anything.

The work then routes around it — grep the spilled file, reconstruct the few
entries that mattered — which is slower, lossy, and means the orientation the
room was built to provide is not what anyone actually uses.

Nothing here is a bug in what the room stores. It is that retrieval has no
bound, and a durable log without a bound eventually stops being readable.

## Plan

1. Give `room_status` and `room_inbox` a bounded default: a capped number of the
   most recent entries.
2. State the bound in the response. A caller must not have to infer whether it
   received everything.
3. Report what was elided, as a count. Without it, a truncated room and a quiet
   room look identical, and an agent that cannot tell those apart will make
   confident wrong decisions about whether it has been assigned anything.
4. Keep the omitted entries reachable through an explicit limit or offset, so the
   bound is a default and never a loss.
5. Retain the newest by default. Orientation is about current state; history is
   what the explicit call is for.
6. Leave a small room byte-identical to today, so the change is invisible until
   it is needed.

## Not in scope

Summarising, ranking or filtering entries by relevance — that is a judgement this
packet should not make, and a bound is the whole fix. Changing what is stored,
retention, or the schema. Changing `room_recent` or `room_thread`, which take
their own explicit limits already. Deleting anything.

## Verification

**Tier 1 — mechanical.**

```
python -m pytest -q -m "integration or not integration" tests/test_agent_room_cli.py tests/test_mcp_agent_room_server.py
python -m ruff check gateway/agent_room_cli.py mcp/agent_room/server.py
```

Today these collect 5 and 10 tests and pass, and neither bounds a response. The
new cases must include a room large enough to truncate, asserting both the
elision count and that the omitted entries are retrievable — a test that only
checks the cap would pass on an implementation that silently drops them.

**Tier 2 — running app.** Not applicable; no user-visible surface changes.

**Tier 3 — product acceptance.** Not applicable.

## Stop condition

Stop and escalate if a bounded reply cannot report how many entries it left out.
A truncation that does not announce itself is worse than the current oversized
reply: today an agent is defeated loudly and knows it, whereas a silent
truncation would let it conclude the room is empty and act on that.

## Recovery

Read-path only; nothing stored changes, so reverting `gateway/agent_room_cli.py`
and `mcp/agent_room/server.py` to `HEAD` fully restores current behaviour and no
message can be lost by this packet failing at any point.
