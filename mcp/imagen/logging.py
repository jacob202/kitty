"""Structured logger for the imagen package.

One named logger so all imagen output is filterable. No payload dumps per
the AGENTS.md prime directive — engine name and attempt number only.
"""

import logging

log = logging.getLogger("kitty.imagen")
