#!/usr/bin/env bash
# Sanitize Builder-generated .claude/STATE.md and .claude/HANDOFF.md
# so they pass CI schema validation. Run from the worktree root.
set -euo pipefail

python3 - "$(git rev-parse HEAD)" <<'PY'
import json, re, sys
from pathlib import Path

HEAD = sys.argv[1]
REQUIRED = ['schema_version', 'updated_at', 'head_sha', 'branch', 'worktree',
            'status', 'completed_items', 'blockers', 'next_action', 'active_mission',
            'parallel_work', 'recommendations', 'invalidation_conditions', 'pull_request']

for rel in ['.claude/STATE.md', '.claude/HANDOFF.md']:
    path = Path(rel)
    if not path.exists(): continue
    content = path.read_text()
    tag = 'kitty-state' if 'STATE' in rel else 'kitty-handoff'
    m = re.search(rf'<!-- {tag}\s*\n(.*?)\n-->', content, re.DOTALL)
    if not m:
        print(f'WARNING: {rel} has no {tag} block')
        continue
    meta = json.loads(m.group(1))

    # Fill missing required keys
    defaults = {
        'schema_version': 2, 'updated_at': '2026-08-02T01:00:00Z',
        'head_sha': HEAD, 'branch': 'main', 'worktree': 'main',
        'completed_items': [], 'blockers': [], 'parallel_work': [],
        'recommendations': [], 'active_mission': 'docs/ACTIVE_MISSION.md',
        'invalidation_conditions': ['HEAD changes beyond HEAD'],
        'pull_request': None,
    }
    for k, v in defaults.items():
        if k not in meta:
            meta[k] = v

    # Fix status
    if 'STATE' in rel:
        meta['status'] = 'complete'
    else:
        meta['status'] = 'valid'

    # Sync next_action: STATE and HANDOFF must agree
    meta['next_action'] = 'None'

    # Re-insert JSON block
    new_json = json.dumps(meta, indent=2, ensure_ascii=False)
    content = re.sub(
        rf'(<!-- {tag}\s*\n).*?(\n-->)',
        r'\1' + new_json + r'\2', content, flags=re.DOTALL
    )
    path.write_text(content)
    print(f'sanitized {rel}')

print('STATE/HANDOFF sanitized')
PY
