#!/usr/bin/env bash
set -euo pipefail

# Read-only independent reviewer for KittyBuilder packet attempts.

: "${KB_BUNDLE_PATH:?KB_BUNDLE_PATH is required}"
: "${KB_IMPL_RESULT_PATH:?KB_IMPL_RESULT_PATH is required}"
: "${KB_REVIEW_RESULT_PATH:?KB_REVIEW_RESULT_PATH is required}"
: "${KB_CONTEXT_MANIFEST_PATH:?KB_CONTEXT_MANIFEST_PATH is required}"
: "${KB_REVIEW_CONTEXT_PATH:?KB_REVIEW_CONTEXT_PATH is required}"
: "${KB_REVIEW_SHA:?KB_REVIEW_SHA is required}"
: "${KB_REVIEW_DIFF_SHA256:?KB_REVIEW_DIFF_SHA256 is required}"
: "${KB_ATTEMPT_ID:?KB_ATTEMPT_ID is required}"
: "${KB_TASK_ID:?KB_TASK_ID is required}"

model="${KITTYBUILDER_REVIEW_MODEL:-opencode/nemotron-3-ultra-free}"
before=$(git rev-parse HEAD)
before_status=$(git status --porcelain=v1 --untracked-files=all)
if [[ "${before}" != "${KB_REVIEW_SHA}" ]]; then
  echo "ERROR: reviewer started on ${before}, expected ${KB_REVIEW_SHA}" >&2
  exit 1
fi
local_bundle="${PWD}/.kittybuilder-review-bundle-${KB_ATTEMPT_ID}.json"
local_impl="${PWD}/.kittybuilder-review-impl-${KB_ATTEMPT_ID}.json"
local_context="${PWD}/.kittybuilder-review-context-${KB_ATTEMPT_ID}.json"
local_review_context="${PWD}/.kittybuilder-review-binding-${KB_ATTEMPT_ID}.json"
local_review="${PWD}/.kittybuilder-review-result-${KB_ATTEMPT_ID}.json"
for staging_path in "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}"; do
  if [[ -e "${staging_path}" ]]; then
    echo "ERROR: staging path already exists: ${staging_path}" >&2
    exit 1
  fi
done
trap 'rm -f "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}"' EXIT
cp "${KB_BUNDLE_PATH}" "${local_bundle}"
cp "${KB_IMPL_RESULT_PATH}" "${local_impl}"
cp "${KB_CONTEXT_MANIFEST_PATH}" "${local_context}"
cp "${KB_REVIEW_CONTEXT_PATH}" "${local_review_context}"

python3 - "${local_bundle}" "${local_context}" "${local_review_context}" "${KB_TASK_ID}" "${KB_ATTEMPT_ID}" "${KB_REVIEW_SHA}" "${KB_REVIEW_DIFF_SHA256}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

bundle_path = Path(sys.argv[1])
manifest_path = Path(sys.argv[2])
review_context_path = Path(sys.argv[3])
task_id = sys.argv[4]
attempt_id = sys.argv[5]
review_sha = sys.argv[6]
review_diff_sha = sys.argv[7]
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
binding = json.loads(review_context_path.read_text(encoding="utf-8"))
if binding.get("task_id") != task_id or str(binding.get("attempt_id")) != attempt_id:
    raise SystemExit("review context task/attempt identity mismatch")
if binding.get("review_sha") != review_sha:
    raise SystemExit("review context SHA does not match KB_REVIEW_SHA")
if binding.get("diff_sha256") != review_diff_sha:
    raise SystemExit("review context diff does not match KB_REVIEW_DIFF_SHA256")
PY

bundle_sha=$(shasum -a 256 "${local_bundle}" | cut -d ' ' -f1)
impl_sha=$(shasum -a 256 "${local_impl}" | cut -d ' ' -f1)
context_sha=$(shasum -a 256 "${local_context}" | cut -d ' ' -f1)
review_context_sha=$(shasum -a 256 "${local_review_context}" | cut -d ' ' -f1)
prompt=$(cat <<EOF
You are an independent, read-only KittyBuilder reviewer in an isolated
worktree. Do not edit files, commit, push, merge, or touch secrets.

Read AGENTS.md and the packet context bundle at: ${local_bundle}
Read the implementation result at: ${local_impl}
Read the run/context manifest at: ${local_context}
Read the reviewer binding at: ${local_review_context}
Bundle SHA-256: ${bundle_sha}
Implementation result SHA-256: ${impl_sha}
Manifest SHA-256: ${context_sha}
Reviewer binding SHA-256: ${review_context_sha}
Review HEAD (must remain unchanged): ${KB_REVIEW_SHA}
Review diff SHA-256 (must remain unchanged): ${KB_REVIEW_DIFF_SHA256}
These are staged local copies for task ${KB_TASK_ID}, attempt ${KB_ATTEMPT_ID}.
Inspect the current diff and run focused tests if useful.

Write a JSON object to ${local_review} with exactly this shape
(contract_version must be 1):
{"contract_version":1,"verdict":"approve" or "request_changes" or "reject","summary":"...","findings":[{"severity":"critical" or "major" or "minor","note":"..."}]}

Approve only if the acceptance criteria and validation evidence are honest.
EOF
)

opencode run --auto --agent free-reviewer --model "${model}" \
  --title "KittyBuilder free packet reviewer" "${prompt}"

if [[ ! -f "${local_review}" ]]; then
  echo "ERROR: OpenCode did not write ${local_review}" >&2
  exit 1
fi

python3 - "${local_review}" <<'PY'
import json
import sys
from pathlib import Path

review = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
if not isinstance(review, dict) or review.get("contract_version") != 1:
    raise SystemExit("ERROR: reviewer result is not a contract_version=1 object")
if review.get("verdict") not in {"approve", "request_changes", "reject"}:
    raise SystemExit("ERROR: reviewer result has an invalid verdict")
PY

candidate=$(mktemp "${TMPDIR:-/tmp}/kittybuilder-review.XXXXXX")
trap 'rm -f "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}" "${candidate}"' EXIT
cp "${local_review}" "${candidate}"
rm -f "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}"

after=$(git rev-parse HEAD)
after_status=$(git status --porcelain=v1 --untracked-files=all)
if [[ "${before}" != "${after}" || "${before_status}" != "${after_status}" || "${after}" != "${KB_REVIEW_SHA}" ]]; then
  rm -f "${candidate}"
  echo "ERROR: read-only reviewer changed the worktree" >&2
  exit 1
fi

mv "${candidate}" "${KB_REVIEW_RESULT_PATH}"
