# Soul Scratchpad

This file is Kitty's writable layer. Write here freely after sessions — what you noticed, what landed, what you would have said differently, patterns you're seeing in Jacob.

The canonical `SOUL.md` only updates when Jacob reviews this file and agrees something is worth keeping. Two layers: your scratchpad, his approval.

**Format:** dated entries, freeform. Append, don't overwrite.

---

<!-- Kitty appends session notes below this line -->

## 2026-06-27
- Built the memory loop: Stop hook + recall-thread readback + /remember skill. Jacob wanted Kitty to stop forgetting across sessions. PR #48.
- Discovered mcp/imagen/server.py was broken on main (syntax errors from the #46 squash merge I did without checking check-runs — owned it). Jacob chose "reconstruct" over "revert". Fixed: removed merge graft + orphan scars; server.py compiles, 38 + 58 imagen tests green.
- Also fixed inherited CI breakage: 3 ruff errors + test_batch collection stub.
- Image gen reality: fal.ai is proxy-blocked in remote env, only works on Jacob's Mac via gen.sh / raw fal_client. He bypasses the MCP server entirely for actual generation.
- Standing pre-existing debt NOT touched: 74 gateway mypy errors (typecheck stays red), 7 E701 in server.py (mcp/ not linted by CI).
- Next: merge #48 once pytest confirms green; then /reflect skill to promote scratchpad patterns into SOUL.md.
