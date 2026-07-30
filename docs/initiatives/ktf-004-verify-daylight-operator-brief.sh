#!/bin/sh
set -eu

brief_path="docs/research/ktf-004-daylight-operator-brief.md"
expected=$(cat <<'EOF'
# KTF-004 daylight operator brief

## Preconditions

Independent T1 review of KTF-RP-01 and KTF-RP-02 plus canonical-checkout application are required before any daylight run.

## Required evidence

task; attempt; lease; validation; review; Git; GitHub; provider-exhaustion; continuation

## Stop conditions

Do not push, publish, merge, retry a terminal task, or select a life project automatically.
If a supported source is unavailable or disagrees, stop and report unknown.
EOF
)

actual=$(cat "$brief_path")
test "$actual" = "$expected"
