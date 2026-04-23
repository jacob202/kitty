"""AgentCompany source modules."""

import sys
from pathlib import Path

# Add project paths for imports
_project_root = Path(__file__).parent.parent
if str(_project_root) not in sys.path:
    sys.path.insert(0, str(_project_root))
if str(_project_root / "scripts") not in sys.path:
    sys.path.insert(0, str(_project_root / "scripts"))


def kitty_cli_alt():
    """Entry point for kitty-cli (kitty_cli.py)."""
    from kitty_cli import app

    app()


def kitty_cli():
    """Backward-compatible entry point for the active CLI."""
    kitty_cli_alt()


def kitty_web():
    """Entry point for kitty-web."""
    from web import main

    main()
