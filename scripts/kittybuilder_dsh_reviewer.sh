#!/usr/bin/env bash
set -euo pipefail

budget_started=${SECONDS}

# Read-only independent DeepSeek Harness reviewer for KittyBuilder packet attempts.

: "${KB_BUNDLE_PATH:?KB_BUNDLE_PATH is required}"
: "${KB_IMPL_RESULT_PATH:?KB_IMPL_RESULT_PATH is required}"
: "${KB_REVIEW_RESULT_PATH:?KB_REVIEW_RESULT_PATH is required}"
: "${KB_CONTEXT_MANIFEST_PATH:?KB_CONTEXT_MANIFEST_PATH is required}"
: "${KB_REVIEW_CONTEXT_PATH:?KB_REVIEW_CONTEXT_PATH is required}"
: "${KB_REVIEW_SHA:?KB_REVIEW_SHA is required}"
: "${KB_REVIEW_DIFF_SHA256:?KB_REVIEW_DIFF_SHA256 is required}"
: "${KB_ATTEMPT_ID:?KB_ATTEMPT_ID is required}"
: "${KB_TASK_ID:?KB_TASK_ID is required}"

adapter_agent="${KITTYBUILDER_REVIEW_AGENT:-free-reviewer}"
if [[ "${adapter_agent}" == "paid-reviewer" ]]; then
  lane_label="paid"
else
  lane_label="free"
fi

# Route selection may force one reviewer model; otherwise the free adapter
# remains on its zero-cost default.
if [[ -n "${KITTYBUILDER_REVIEW_MODEL:-}" ]]; then
  models=("${KITTYBUILDER_REVIEW_MODEL}")
elif [[ -n "${KITTYBUILDER_REVIEW_MODELS:-}" ]]; then
  read -r -a models <<<"${KITTYBUILDER_REVIEW_MODELS}"
else
  models=(
    "openrouter/free"
  )
fi
before=$(git rev-parse HEAD)
before_status=$(git status --porcelain=v1 --untracked-files=all -- . ':(exclude).omo/run-continuation/**')
if [[ "${before}" != "${KB_REVIEW_SHA}" ]]; then
  echo "ERROR: reviewer started on ${before}, expected ${KB_REVIEW_SHA}" >&2
  exit 1
fi
local_bundle="${PWD}/.kittybuilder-review-bundle-${KB_ATTEMPT_ID}.json"
local_impl="${PWD}/.kittybuilder-review-impl-${KB_ATTEMPT_ID}.json"
local_context="${PWD}/.kittybuilder-review-context-${KB_ATTEMPT_ID}.json"
local_review_context="${PWD}/.kittybuilder-review-binding-${KB_ATTEMPT_ID}.json"
local_review="${PWD}/.kittybuilder-review-result-${KB_ATTEMPT_ID}.json"
local_prompt="${PWD}/.kittybuilder-review-prompt-${KB_ATTEMPT_ID}.txt"
for staging_path in "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}" "${local_prompt}"; do
  if [[ -e "${staging_path}" ]]; then
    echo "ERROR: staging path already exists: ${staging_path}" >&2
    exit 1
  fi
done
trap 'rm -f "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}" "${local_prompt}"' EXIT
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
base_sha=$(python3 - "${local_context}" <<'PY_BASE'
import json
import sys
from pathlib import Path

manifest = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
base = ((manifest.get("lease") or {}).get("base_sha") or "").strip()
if len(base) != 40 or any(c not in "0123456789abcdef" for c in base):
    raise SystemExit("ERROR: reviewer run manifest has no valid lease.base_sha")
print(base)
PY_BASE
)
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
Packet base SHA: ${base_sha}
Review HEAD (must remain unchanged): ${KB_REVIEW_SHA}
Review diff SHA-256 (must remain unchanged): ${KB_REVIEW_DIFF_SHA256}
These are staged local copies for task ${KB_TASK_ID}, attempt ${KB_ATTEMPT_ID}.
The implementation is already committed by trusted Builder orchestration. Inspect
the committed packet diff from ${base_sha}..${KB_REVIEW_SHA}; do not treat a diff
from Review HEAD to itself as the packet diff, and never run git add/stage/commit. Run focused
tests if useful.

You are running under a read-only filesystem policy. Do not write or edit any
file. After deciding the verdict, make your FINAL RESPONSE exactly one JSON object
with this shape (contract_version must be 1), with no Markdown fence or prose:
{"contract_version":1,"verdict":"approve" or "request_changes" or "reject","summary":"...","findings":[{"severity":"critical" or "major" or "minor","note":"..."}]}

Approve only if the acceptance criteria and validation evidence are honest.
EOF
)
printf '%s' "${prompt}" > "${local_prompt}"

fingerprint() {
  git rev-parse HEAD
  git status --porcelain=v1 --untracked-files=all -- . ':(exclude).omo/run-continuation/**'
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMEOUT_RUNNER="${SCRIPT_DIR}/run_with_timeout.py"
DSH_LAUNCHER="${SCRIPT_DIR}/kittybuilder_dsh.sh"
review_budget=${KB_REVIEW_TIMEOUT_SECONDS:-240}

# The ladder exists for models that never get started, and those fail within
# seconds. Dividing the budget by the model count instead gave the model doing
# the actual review a fraction of the time; the same defect cost the worker a
# half-finished packet on 2026-08-31. The reserve keeps enough budget left for
# the review file to be written.
model_timeout() {
  local elapsed=$((SECONDS - budget_started))
  local reserve=$((review_budget / 10))
  (( reserve < 60 )) || reserve=60
  local remaining=$((review_budget - elapsed - reserve))
  (( remaining > 0 )) || remaining=1
  echo "${remaining}"
}

# A reviewer model may hand off to the next free model only when it failed
# cleanly: no review written and no worktree mutation. A written review file
# is never discarded in favour of another model, and any mutation is fatal.
chosen_model=""
for model in "${models[@]}"; do
  attempt_before="$(fingerprint)"
  slot_seconds=$(model_timeout)
  echo "=== ${lane_label} reviewer attempt: ${model} (${slot_seconds}s slot) ==="
  set +e
  review_output=$(python3 "${TIMEOUT_RUNNER}" "${slot_seconds}" \
    bash "${DSH_LAUNCHER}" --preset kitty-sprint --provider openrouter --model "${model}" \
    --permission read-only --task-file "${local_prompt}" </dev/null)
  rc=$?
  set -e
  if [[ ${rc} -eq 124 ]]; then
    echo "WARNING: reviewer ${model} timed out after ${slot_seconds}s." >&2
  fi
  if [[ ${rc} -eq 0 && -n "${review_output}" ]]; then
    if REVIEW_OUTPUT="${review_output}" python3 - "${local_review}" <<'PY_REVIEW_OUTPUT'
import json
import os
import sys
from pathlib import Path

raw = os.environ.get("REVIEW_OUTPUT", "").strip()
try:
    review = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(1)
if not isinstance(review, dict) or review.get("contract_version") != 1:
    raise SystemExit(1)
if review.get("verdict") not in {"approve", "request_changes", "reject"}:
    raise SystemExit(1)
Path(sys.argv[1]).write_text(json.dumps(review), encoding="utf-8")
PY_REVIEW_OUTPUT
    then
      chosen_model="${model}"
      break
    fi
    rm -f "${local_review}"
    echo "WARNING: reviewer ${model} returned invalid review JSON; trying the next ${lane_label} model." >&2
  fi
  attempt_after="$(fingerprint)"
  if [[ "${attempt_before}" != "${attempt_after}" ]]; then
    echo "ERROR: read-only reviewer ${model} changed the worktree" >&2
    exit 1
  fi
  echo "WARNING: reviewer ${model} exited ${rc} without a review; trying the next ${lane_label} model." >&2
done

if [[ -z "${chosen_model}" ]]; then
  echo "ERROR: every reviewer model failed without producing ${local_review}: ${models[*]}" >&2
  exit 75
fi
echo "Review completed with ${chosen_model}."

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

# A short human-readable note that Builder, Kitty, and Jacob can all read
# alongside the structured review contract. KB_REVIEW_NOTE_PATH is runner-owned
# and optional; the note is derived deterministically from the validated review.
if [[ -n "${KB_REVIEW_NOTE_PATH:-}" ]]; then
  python3 - "${local_review}" "${KB_REVIEW_NOTE_PATH}" "${KB_REVIEW_SHA}" "${chosen_model}" <<'PY'
import json
import sys
from pathlib import Path

review = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
note_path = Path(sys.argv[2])
sha = sys.argv[3]
model = sys.argv[4]
lines = [
    "# KittyBuilder review note",
    "",
    f"- Reviewed commit: `{sha}`",
    f"- Verdict: {review.get('verdict')}",
    f"- Model: {model}",
    "",
    "## Summary",
    "",
    str(review.get("summary", "")),
]
findings = review.get("findings")
if isinstance(findings, list) and findings:
    lines += ["", "## Findings", ""]
    for item in findings:
        if isinstance(item, dict):
            lines.append(f"- [{item.get('severity', 'note')}] {item.get('note', '')}")
        else:
            lines.append(f"- {item}")
lines.append("")
note_path.write_text("\n".join(lines), encoding="utf-8")
PY
fi

candidate=$(mktemp "${TMPDIR:-/tmp}/kittybuilder-review.XXXXXX")
trap 'rm -f "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}" "${local_prompt}" "${candidate}"' EXIT
cp "${local_review}" "${candidate}"
rm -f "${local_bundle}" "${local_impl}" "${local_context}" "${local_review_context}" "${local_review}" "${local_prompt}"

after=$(git rev-parse HEAD)
after_status=$(git status --porcelain=v1 --untracked-files=all -- . ':(exclude).omo/run-continuation/**')
if [[ "${before}" != "${after}" || "${before_status}" != "${after_status}" || "${after}" != "${KB_REVIEW_SHA}" ]]; then
  rm -f "${candidate}"
  echo "ERROR: read-only reviewer changed the worktree" >&2
  exit 1
fi

# Seatbelt denies write() on a descriptor a process inherited across execve,
# so `cat src > dest` creates the runner-owned result file and then fails with
# "cat: stdout: Operation not permitted" — which is what happened on
# 2026-08-31 to the first worker that ever finished a packet: 52/52 tests
# green, and the result never reached the runner. A process that opens the
# destination itself is allowed, so hand the file over through python3, which
# this adapter already depends on.
handoff() {
  python3 - "$1" "$2" <<'HANDOFF_PY'
import sys
from pathlib import Path

Path(sys.argv[2]).write_bytes(Path(sys.argv[1]).read_bytes())
HANDOFF_PY
}

handoff "${candidate}" "${KB_REVIEW_RESULT_PATH}"
rm -f "${candidate}"
