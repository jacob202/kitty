#!/usr/bin/env bash
set -euo pipefail

# Run one Kitty task card through free OpenCode models only. A failed model may
# hand off to the next provider only when it left both HEAD and the worktree
# unchanged. Successful implementation is followed by a separate read-only
# free-model review. This script never pushes or merges.

usage() {
  cat <<'EOF'
Usage:
  ./scripts/opencode_free_train.sh <task-card.md>

Optional environment variables:
  OPENCODE_FREE_MODEL         Force one builder model instead of the ladder.
  OPENCODE_FREE_REVIEW_MODEL  Force one reviewer model.
  OPENCODE_FREE_LOG_DIR       Directory for transcripts (defaults to /tmp).
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ $# -ne 1 ]]; then
  usage >&2
  exit 2
fi

if ! command -v git >/dev/null 2>&1; then
  echo "ERROR: git is required." >&2
  exit 1
fi
if ! command -v opencode >/dev/null 2>&1; then
  echo "ERROR: opencode is required." >&2
  exit 1
fi

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "${repo_root}" ]]; then
  echo "ERROR: run this inside an isolated Kitty git worktree." >&2
  exit 1
fi
cd "${repo_root}"

task_file="$1"
if [[ ! -f "${task_file}" ]]; then
  echo "ERROR: task card not found: ${task_file}" >&2
  exit 1
fi

if [[ -n "$(git status --porcelain=v1 --untracked-files=all)" ]]; then
  echo "ERROR: free build train requires a clean isolated worktree at launch." >&2
  git status --short --branch >&2
  exit 1
fi

fingerprint() {
  printf '%s\n' "$(git rev-parse HEAD)"
  git status --porcelain=v1 --untracked-files=all
}

initial_fingerprint="$(fingerprint)"
timestamp="$(date +%Y%m%d-%H%M%S)"
log_root="${OPENCODE_FREE_LOG_DIR:-/tmp/kitty-opencode-free-${timestamp}}"
mkdir -p "${log_root}"
prompt="$(cat "${task_file}")"

builder_models=(
  "opencode/deepseek-v4-flash-free"
  "opencode/mimo-v2.5-free"
  "opencode/nemotron-3-ultra-free"
  "opencode/north-mini-code-free"
  "openrouter/poolside/laguna-xs-2.1:free"
  "openrouter/tencent/hy3:free"
  "openrouter/free"
)

review_models=(
  "opencode/nemotron-3-ultra-free"
  "opencode/mimo-v2.5-free"
  "opencode/north-mini-code-free"
  "openrouter/tencent/hy3:free"
  "openrouter/free"
)

if [[ -n "${OPENCODE_FREE_MODEL:-}" ]]; then
  builder_models=("${OPENCODE_FREE_MODEL}")
fi
if [[ -n "${OPENCODE_FREE_REVIEW_MODEL:-}" ]]; then
  review_models=("${OPENCODE_FREE_REVIEW_MODEL}")
fi

builder_model=""
for model in "${builder_models[@]}"; do
  before="$(fingerprint)"
  safe_name="$(printf '%s' "${model}" | tr '/:' '__')"
  log_file="${log_root}/builder-${safe_name}.log"

  echo
  echo "=== Free builder attempt: ${model} ==="
  echo "Transcript: ${log_file}"

  set +e
  opencode run \
    --auto \
    --agent free-builder \
    --model "${model}" \
    --title "Kitty free build: $(basename "${task_file}")" \
    "${prompt}" 2>&1 | tee "${log_file}"
  rc=${PIPESTATUS[0]}
  set -e

  after="$(fingerprint)"
  if [[ ${rc} -eq 0 && "${after}" != "${before}" ]]; then
    builder_model="${model}"
    echo "Builder completed with ${model}."
    break
  fi

  if [[ "${after}" != "${before}" ]]; then
    echo "ERROR: ${model} stopped after changing HEAD or the worktree." >&2
    echo "No automatic fallback will run over partial work." >&2
    echo "Inspect the worktree and ${log_file}." >&2
    exit 3
  fi

  if [[ ${rc} -eq 0 ]]; then
    echo "WARNING: ${model} returned success without changing the task; trying the next free model." >&2
  else
    echo "WARNING: ${model} failed cleanly with exit ${rc}; trying the next free model." >&2
  fi
done

if [[ -z "${builder_model}" ]]; then
  echo "ERROR: every free builder model failed or produced no implementation." >&2
  echo "Transcripts: ${log_root}" >&2
  exit 4
fi

review_prompt="Review the implementation for the task card at ${task_file}. Compare the current branch against its merge base with origin/main, inspect all changed files, and run the relevant focused tests if useful. The builder model was ${builder_model}; you must be independent and read-only. Return APPROVE or BLOCK as the first word."
reviewed=0
approved=0
for model in "${review_models[@]}"; do
  if [[ "${model}" == "${builder_model}" ]]; then
    continue
  fi

  before_review="$(fingerprint)"
  safe_name="$(printf '%s' "${model}" | tr '/:' '__')"
  log_file="${log_root}/review-${safe_name}.log"

  echo
  echo "=== Free reviewer attempt: ${model} ==="
  echo "Transcript: ${log_file}"

  set +e
  opencode run \
    --auto \
    --agent free-reviewer \
    --model "${model}" \
    --title "Kitty free review: $(basename "${task_file}")" \
    "${review_prompt}" 2>&1 | tee "${log_file}"
  rc=${PIPESTATUS[0]}
  set -e

  after_review="$(fingerprint)"
  if [[ "${after_review}" != "${before_review}" ]]; then
    echo "ERROR: read-only reviewer ${model} changed HEAD or the worktree." >&2
    echo "Review is invalid; inspect ${log_file}." >&2
    exit 5
  fi

  if [[ ${rc} -ne 0 ]]; then
    echo "WARNING: reviewer ${model} failed with exit ${rc}; trying another free reviewer." >&2
    continue
  fi

  reviewed=1
  first_decision="$(grep -Eo 'APPROVE|BLOCK' "${log_file}" | head -n 1 || true)"
  if [[ "${first_decision}" == "APPROVE" ]]; then
    approved=1
    echo "Independent free review approved the implementation."
  else
    echo "Review did not approve the implementation. Inspect ${log_file}." >&2
  fi
  break
done

if [[ ${reviewed} -eq 0 ]]; then
  echo "ERROR: no independent free reviewer completed successfully." >&2
  echo "Implementation remains in the worktree for inspection." >&2
  exit 6
fi
if [[ ${approved} -eq 0 ]]; then
  echo "BLOCKED: implementation completed but the independent review did not approve it." >&2
  exit 7
fi

if [[ "$(fingerprint)" == "${initial_fingerprint}" ]]; then
  echo "ERROR: build train ended without a changed commit or worktree." >&2
  exit 8
fi

echo
echo "FREE BUILD TRAIN COMPLETE"
echo "Builder: ${builder_model}"
echo "Logs: ${log_root}"
echo "No push or merge was performed."
git status --short --branch
