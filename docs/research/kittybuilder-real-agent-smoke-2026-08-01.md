# KittyBuilder real-agent smoke evidence (2026-08-01)

Starting main SHA: bcae5f28fcb5a11573faeea29862231a9335b7fa
Provider: opencode
Model: opencode/deepseek-v4-flash-free
Initiative ID: kittybuilder-real-agent-smoke-2026-08-01-v1
Packet ID: SMOKE-01-create-evidence-file
Task ID: kb_msaumzv4_bfae
Attempt ID: 1
Attempt number: 1
Worker ID: opencode-free

## What KittyBuilder did

1. An operator dispatched this packet to KittyBuilder as a free-model task with a one-attempt budget and zero paid spend.
2. KittyBuilder created an isolated git worktree for the task from the recorded starting main SHA and ran the worker inside it.
3. The free worker authored this file inside that worktree, within the packet's allowed path docs/research/.
4. The worker committed the file on the task branch with the packet marker in the commit subject.
5. This file is disposable smoke evidence for the delivery-path audit and makes no claim about merging or production behavior.
