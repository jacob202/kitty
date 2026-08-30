#!/usr/bin/env bash
# Kitty preflight — verify the environment before a long or unattended run.
#
# CLAUDE.md has listed `bash scripts/preflight.sh` as the first command in its
# Commands block for months while the file did not exist, so the documented
# entrypoint failed for anyone who tried it. This is that file.
#
# It checks the things that have actually cost time here: a checkout that is not
# the canonical one, git auth that cannot push, stale background workers holding
# ports and databases, a running UI built from a different commit than the tree,
# a Builder schedule that was never loaded, and CI check names assumed from an
# earlier session. It reports; it does not repair, install, or mutate state.
#
# Exit 0 = safe to proceed (warnings may still be printed).
# Exit 1 = at least one hard check failed; fix it before a long run.
#
# Usage: bash scripts/preflight.sh [--quiet]

set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

CANONICAL_CHECKOUT="${KITTY_EXPECTED_CANONICAL_CHECKOUT:-$HOME/Projects/kitty}"
QUIET=0
[[ "${1:-}" == "--quiet" ]] && QUIET=1

FAILURES=0
WARNINGS=0

ok()   { [[ $QUIET -eq 1 ]] || printf '  ok    %s\n' "$1"; }
warn() { WARNINGS=$((WARNINGS + 1)); printf '  warn  %s\n' "$1"; }
fail() { FAILURES=$((FAILURES + 1)); printf '  FAIL  %s\n' "$1"; }
section() { [[ $QUIET -eq 1 ]] || printf '\n%s\n' "$1"; }

http_ok() { curl -fsS --max-time 3 -o /dev/null "$1" 2>/dev/null; }

# ── Checkout identity ───────────────────────────────────────────────────────
section "Checkout"

# Compared case-insensitively: macOS resolves ~/projects and ~/Projects to the
# same directory, and the two spellings appear interchangeably in this repo.
if [[ "$(printf '%s' "${ROOT_DIR}" | tr '[:upper:]' '[:lower:]')" \
   == "$(printf '%s' "${CANONICAL_CHECKOUT}" | tr '[:upper:]' '[:lower:]')" ]]; then
  ok "canonical checkout ${ROOT_DIR}"
elif [[ "${ROOT_DIR}" == *"/.worktrees/"* ]]; then
  warn "running from a linked worktree (${ROOT_DIR}); Builder state and launchd installs belong to the canonical checkout"
elif [[ "${ROOT_DIR}" == *"/Desktop/"* || "${ROOT_DIR}" == *ackup* ]]; then
  fail "this looks like a Desktop or backup copy (${ROOT_DIR}); stop and confirm with Jacob before changing anything"
else
  warn "checkout ${ROOT_DIR} is not the expected ${CANONICAL_CHECKOUT}"
fi

if BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null)"; then
  ok "branch ${BRANCH} at $(git rev-parse --short HEAD)"
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    warn "working tree is dirty ($(git status --porcelain | wc -l | tr -d ' ') path(s)); run git status before a long run"
  fi
else
  fail "not a git repository"
fi

# ── Toolchain ───────────────────────────────────────────────────────────────
section "Toolchain"

for tool in git curl jq node npm; do
  if command -v "$tool" >/dev/null 2>&1; then
    ok "$tool present"
  else
    fail "$tool not on PATH"
  fi
done

if [[ -x "${ROOT_DIR}/venv/bin/python" ]]; then
  ok "repo venv python $("${ROOT_DIR}/venv/bin/python" -V 2>&1 | awk '{print $2}')"
elif command -v python3.12 >/dev/null 2>&1; then
  warn "no repo venv at venv/bin/python; falling back to system python3.12"
else
  fail "neither venv/bin/python nor python3.12 is available"
fi

# ── Git auth ────────────────────────────────────────────────────────────────
section "Git auth"

if [[ -n "${GITHUB_TOKEN:-}" ]]; then
  warn "GITHUB_TOKEN is set in this shell; it can shadow keyring auth and push as the wrong identity"
else
  ok "no ambient GITHUB_TOKEN"
fi

if command -v gh >/dev/null 2>&1; then
  if gh auth status >/dev/null 2>&1; then
    ok "gh authenticated as $(gh api user --jq .login 2>/dev/null || echo 'unknown login')"
  else
    fail "gh is installed but not authenticated; run: gh auth login"
  fi
else
  fail "gh not on PATH"
fi

if git config --get credential.helper >/dev/null 2>&1; then
  ok "git credential helper configured"
else
  warn "no git credential helper; if a push fails use: git -c credential.helper='!gh auth git-credential' push"
fi

# ── Stale background work ───────────────────────────────────────────────────
# A leftover worker holds the queue database and the ports, and its output shows
# up in the next run's logs as if it belonged there.
section "Background processes"

check_stale() {
  local label="$1" pattern="$2"
  local pids
  pids="$(pgrep -f "$pattern" 2>/dev/null | tr '\n' ' ' | sed 's/ $//')"
  if [[ -n "$pids" ]]; then
    warn "$label still running (pid ${pids}); reap it before a new run"
  else
    ok "no stale $label"
  fi
}

check_stale "pytest process" "pytest"
check_stale "Builder packet worker" "builder .*run-packet|initiative run-packet"
check_stale "opencode worker" "opencode run"

# ── Services ────────────────────────────────────────────────────────────────
section "Services"

if http_ok "http://127.0.0.1:8000/health"; then ok "gateway healthy on :8000"
else warn "gateway not answering on :8000; start with ./kitty up"; fi

if http_ok "http://127.0.0.1:8001/health" || http_ok "http://127.0.0.1:8001/"; then ok "litellm answering on :8001"
else warn "litellm not answering on :8001; start with ./kitty up"; fi

if http_ok "http://127.0.0.1:4000/"; then ok "UI answering on :4000"
else warn "UI not answering on :4000; start with ./kitty ui"; fi

# ── Build identity ──────────────────────────────────────────────────────────
# A UI built from an older commit is invisible at runtime and turns every
# browser observation into a claim about the wrong code.
section "Build identity"

BUILD_STAMP="gateway/kitty-chat/.next/KITTY_SOURCE_SHA"
if [[ -f "$BUILD_STAMP" ]]; then
  BUILD_SHA="$(tr -d '[:space:]' < "$BUILD_STAMP")"
  HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo unknown)"
  if [[ "$BUILD_SHA" == "$HEAD_SHA" ]]; then
    ok "UI build matches HEAD ($(printf '%.8s' "$BUILD_SHA"))"
  else
    warn "UI build is from $(printf '%.8s' "$BUILD_SHA") but HEAD is $(printf '%.8s' "$HEAD_SHA"); rebuild with make ui-build before trusting the screen"
  fi
elif [[ -f "gateway/kitty-chat/.next/BUILD_ID" ]]; then
  warn "UI build has no source stamp, so what it contains cannot be proven; restarting the UI rebuilds and stamps it"
else
  warn "no UI build present; ./kitty ui will build one"
fi

# ── Builder ─────────────────────────────────────────────────────────────────
section "Builder"

if [[ -f "data/kittybuilder/builder_queue.db" ]]; then
  ok "queue database present"
else
  warn "no queue database at data/kittybuilder/builder_queue.db"
fi

SUPERVISOR_LABEL="com.kitty.builder.supervisor"
if launchctl print "gui/$(id -u)/${SUPERVISOR_LABEL}" >/dev/null 2>&1; then
  INTERVAL="$(launchctl print "gui/$(id -u)/${SUPERVISOR_LABEL}" 2>/dev/null \
    | grep -o 'run interval = [0-9]*' | grep -o '[0-9]*' | head -1)"
  ok "supervisor schedule loaded (every ${INTERVAL:-unknown} seconds)"
else
  warn "Builder supervisor schedule is not loaded; nothing will run on its own"
fi

if [[ -f "config/compute_governor.json" ]]; then
  BUDGET="$(jq -r '.weekly_budget_cad // "unset"' config/compute_governor.json 2>/dev/null)"
  ok "spend ceiling CAD ${BUDGET}/week"
else
  warn "no config/compute_governor.json; the governor falls back to its built-in default"
fi

# ── CI expectations ─────────────────────────────────────────────────────────
# Required check names have been restructured mid-session before, which turns
# every merge attempt into confident, wrong triage.
section "CI"

if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  CHECKS="$(gh api "repos/{owner}/{repo}/rulesets" --jq \
    '[.[].id] | join(" ")' 2>/dev/null || true)"
  if [[ -n "${CHECKS// /}" ]]; then
    ok "branch rulesets present (ids: ${CHECKS}); read them before assuming required check names"
  else
    warn "could not read branch rulesets; do not assume last session's required check names"
  fi
else
  warn "skipping CI ruleset read (gh unavailable)"
fi

# ── Continuity ──────────────────────────────────────────────────────────────
section "Continuity"

if [[ -f "scripts/check_continuity_state.py" ]]; then
  PY="${ROOT_DIR}/venv/bin/python"
  [[ -x "$PY" ]] || PY="$(command -v python3.12 || command -v python3)"
  if "$PY" scripts/check_continuity_state.py >/dev/null 2>&1; then
    ok "continuity checkpoint valid"
  else
    warn "continuity checkpoint invalid; run: python3.12 scripts/check_continuity_state.py"
  fi
else
  warn "scripts/check_continuity_state.py missing"
fi

# ── Verdict ─────────────────────────────────────────────────────────────────
printf '\n'
if [[ $FAILURES -gt 0 ]]; then
  printf 'preflight: %d failed, %d warning(s) — fix the failures before a long run\n' "$FAILURES" "$WARNINGS"
  exit 1
fi
printf 'preflight: passed with %d warning(s)\n' "$WARNINGS"
exit 0
