#!/usr/bin/env python3
import os

# Open WebUI stores private chats, tool credentials, logs, and backups. Apply the
# owner-only creation mask before importing any command module so both this
# operator process and every child it launches inherit it.
os.umask(0o077)

from openwebui_tool.cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
