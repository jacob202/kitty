# Implementation Packets

Small, executor-ready planning packets for one-PR slices of Kitty work.

| Packet | Status | Purpose |
|---|---|---|
| [`001-state-spine.md`](001-state-spine.md) | Implemented in PR | Define and implement the first read-only `/state/now` state-composition slice. |

## Packet rules

- One packet should be small enough for one implementation PR.
- Packets describe scope, acceptance, verification, risks, and rollback before code changes begin.
- If a packet conflicts with `docs/DECISIONS.md`, the decision log wins until Jacob updates it.
