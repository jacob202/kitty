"""Pytest child-process bootstrap for Kitty's namespaced safety guard."""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = str(Path(__file__).resolve().parents[2])
_added_root = _ROOT not in sys.path
if _added_root:
    sys.path.insert(0, _ROOT)
try:
    from kitty_test_guard import install_test_guards
finally:
    if _added_root:
        sys.path.remove(_ROOT)

install_test_guards()
