#!/bin/sh
set -eu

report_path="docs/research/ktf-004-current-main-runtime-proof.md"
expected="$(git rev-parse HEAD)"
actual="$(sed -n 's/^inspected HEAD: //p' "$report_path")"

test "$actual" = "$expected"
