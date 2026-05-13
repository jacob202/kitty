#!/bin/bash

load_env_assignments() {
  local file="$1"
  [[ -f "${file}" ]] || return 0

  # Load only dotenv-style assignment lines. Ignore stray shell words like `codex`
  # so helper scripts don't try to execute junk from a hand-edited .env.
  set -a
  eval "$(
    /opt/homebrew/bin/python3.12 - "${file}" <<'PY'
import os
import re
import shlex
import sys
from dotenv import dotenv_values

_VAR_PATTERN = re.compile(r"\$(\w+|\{[^}]+\})")


def expand_with_env(raw_value, env_map):
    def replace_var(match):
        token = match.group(1)
        if token.startswith("{") and token.endswith("}"):
            token = token[1:-1]
        return env_map.get(token, match.group(0))

    return _VAR_PATTERN.sub(replace_var, raw_value)


path = sys.argv[1]
resolved_env = dict(os.environ)
for key, value in dotenv_values(path).items():
    if value is None:
        continue
    if not key:
        continue
    if not (key[0].isalpha() or key[0] == "_"):
        continue
    if not all(ch.isalnum() or ch == "_" for ch in key):
        continue
    expanded_value = expand_with_env(value, resolved_env)
    resolved_env[key] = expanded_value
    print(f"export {key}={shlex.quote(expanded_value)}")
PY
  )"
  set +a
}
