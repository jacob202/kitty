#!/usr/bin/env bash
set -euo pipefail

bad=0
while IFS= read -r -d '' path; do
  base="${path##*/}"
  if [[ "${base}" == ".DS_Store" || "${base}" == $'Icon\r' ]]; then
    printf 'macOS metadata is tracked: %q\n' "${path}" >&2
    bad=1
  fi
done < <(git ls-files -z)

exit "${bad}"
