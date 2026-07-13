#!/usr/bin/env bash
set -euo pipefail

# KittyBuilder worker adapter for free OpenCode routing. The queue runner owns
# the worktree and contract paths; this script only asks OpenCode to implement
# the bounded packet and write the required implementation JSON.

: "${KB_BUNDLE_PATH:?KB_BUNDLE_PATH is required}"
: "${KB_RESULT_PATH:?KB_RESULT_PATH is required}"
: "${KB_CONTEXT_MANIFEST_PATH:?KB_CONTEXT_MANIFEST_PATH is required}"
: "${KB_ATTEMPT_ID:?KB_ATTEMPT_ID is required}"
: "${KB_TASK_ID:?KB_TASK_ID is required}"

model="${KITTYBUILDER_MODEL:-opencode/deepseek-v4-flash-free}"
local_bundle="${PWD}/.kittybuilder-bundle-${KB_ATTEMPT_ID}.json"
local_context="${PWD}/.kittybuilder-context-${KB_ATTEMPT_ID}.json"
local_result="${PWD}/.kittybuilder-result-${KB_ATTEMPT_ID}.json"
for staging_path in "${local_bundle}" "${local_context}" "${local_result}"; do
  if [[ -e "${staging_path}" ]]; then
    echo "ERROR: staging path already exists: ${staging_path}" >&2
    exit 1
  fi
done
cp "${KB_BUNDLE_PATH}" "${local_bundle}"
cp "${KB_CONTEXT_MANIFEST_PATH}" "${local_context}"
trap 'rm -f "${local_bundle}" "${local_context}" "${local_result}"' EXIT

python3 - "${local_bundle}" "${local_context}" "${KB_TASK_ID}" "${KB_ATTEMPT_ID}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

bundle_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
task_id = sys.argv[3]
attempt_id = sys.argv[4]
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
if manifest.get("task_id") != task_id:
    raise SystemExit(f"context manifest task mismatch: {manifest.get('task_id')!r} != {task_id!r}")
if str(manifest.get("attempt_id")) != attempt_id:
    raise SystemExit(f"context manifest attempt mismatch: {manifest.get('attempt_id')!r} != {attempt_id!r}")
actual = hashlib.sha256(bundle_path.read_bytes()).hexdigest()
expected = manifest.get("bundle_sha256")
nested = (manifest.get("context") or {}).get("task_bundle", {}).get("sha256")
if actual != expected or actual != nested:
    raise SystemExit("context bundle hash does not match the run manifest")
PY

bundle_sha=$(shasum -a 256 "${local_bundle}" | cut -d ' ' -f1)
context_sha=$(shasum -a 256 "${local_context}" | cut -d ' ' -f1)
prompt=$(cat <<EOF
You are a KittyBuilder implementation worker in an isolated worktree.

Read AGENTS.md, .claude/HANDOFF.md, and .claude/STATE.md before editing.
Read the packet context bundle at: ${local_bundle}
Read the run/context manifest at: ${local_context}
The local bundle SHA-256 is ${bundle_sha}; the local manifest SHA-256 is ${context_sha}.
Do not read the runner-owned paths outside this worktree.

Implement only the packet in that bundle. Stay within its allowed paths and
acceptance criteria. Do not push, merge, delete files, touch secrets/env files,
or inspect private runtime data. Run the declared validation commands and any
focused tests that materially prove the change.

Before you finish, write a JSON object to ${local_result} with exactly this
shape (contract_version must be 1):
{"contract_version":1,"status":"completed" or "failed","summary":"...","diff_summary":"...","validation":{"passed":true,"output":"..."},"claims":["..."]}

Use status=failed if the implementation or validation cannot honestly pass.
Then give a concise final report.
EOF
)

opencode run --auto --agent free-builder --model "${model}" \
  --title "KittyBuilder free packet worker" "${prompt}"

if [[ ! -f "${local_result}" ]]; then
  echo "ERROR: OpenCode did not write ${local_result}" >&2
  exit 1
fi

python3 - "${local_result}" <<'PY'
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(result, dict) or result.get("contract_version") != 1:
    raise SystemExit("ERROR: worker result is not a contract_version=1 object")
if result.get("status") not in {"completed", "failed"}:
    raise SystemExit("ERROR: worker result has an invalid status")
PY

cp "${local_result}" "${KB_RESULT_PATH}"
