"""AURA personality profile loader."""
from pathlib import Path
from typing import Any

import yaml  # type: ignore

AURA_PATH = Path("data/config/AURA.yaml")

def load_aura(profile_name: str = "default") -> str:
    if not AURA_PATH.exists():
        return "You are a direct, honest assistant. Never flatter."
    with open(AURA_PATH) as f:
        config = yaml.safe_load(f)
    profile = config["profiles"].get(profile_name,
                                      config["profiles"]["default"])
    boundaries = config.get("boundaries", {})
    return (f"You are a digital twin governed by the AURA protocol.\n"
            f"Profile: {profile}\nBoundaries: {boundaries}\n"
            f"Always correct errors; never flatter. Be direct and accurate.")

def get_branding() -> dict[str, Any]:
    """Get branding information from AURA.yaml."""
    import os
    default_branding = {
        "name": "Kitty",
        "assistant_name": "Kitty",
        "coder_name": "KittyCoder",
        "session_prefix": "kitty-squad",
        "exports_dir": os.path.expanduser("~/Documents/Kitty/exports"),
        "contexts_dir": os.path.expanduser("~/Documents/Kitty/contexts"),
        "voice_file": "/tmp/kitty_voice.txt"
    }
    if not AURA_PATH.exists():
        return {
            "name": "Assistant",
            "assistant_name": "Assistant",
            "coder_name": "Coder",
            "session_prefix": "agent-squad",
            "exports_dir": os.path.expanduser("~/Documents/Assistant/exports"),
            "contexts_dir": os.path.expanduser("~/Documents/Assistant/contexts"),
            "voice_file": "/tmp/assistant_voice.txt"
        }
    with open(AURA_PATH) as f:
        config = yaml.safe_load(f)
    branding = config.get("branding", default_branding)
    # Expand paths
    for key in ["exports_dir", "contexts_dir"]:
        if key in branding:
            branding[key] = os.path.expanduser(branding[key])
    return branding
