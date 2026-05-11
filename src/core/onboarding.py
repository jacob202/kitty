"""
Onboarding Module - Guided tour and welcome flow for new users
"""

import json
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from src.core.aura_loader import get_branding

_branding = get_branding()
console = Console()

WELCOME_MESSAGE = f"""
# 🐱 Welcome to {_branding['name']}!

Your AI assistant with **tiered cost system** - always free options available.

## Quick Start

| Command | What It Does |
|---------|-------------|
| `/help` | Show all commands |
| `/status` | Check system status |
| `/mode helpful` | Switch personality |

## Cost Tiers (cheapest to premium)

| Tier | Cost | When Used |
|------|------|-----------|
| claude-code (goose) | **$0** | Free, always available |
| OpenCode Zen | **~$0.01** | Your $20 credit |
| Ollama local | **$0** | Secret mode (say "secret") |
| OpenRouter | **Pay per use** | Fallback |

## Pro Tips

1. **Say "secret"** to use unrestricted local AI (no safety filters)
2. **Say "tier 1" or "tier 2"** to explicitly use cheaper/pricier models
3. **/mode helpful** - Proactive assistant
4. **/mode focus** - Code-first, terse responses
5. **/mode calm** - Grounded, empathetic

## Need Help?

- `/help` - All commands
- `/status` - System health
- Check `docs/QUICK_REFERENCE.md` - Detailed guide

---

*Type `/onboarding` to replay this tour anytime!*
"""

ONBOARDING_STEPS = [
    {
        "step": 1,
        "title": "Getting Started",
        "content": f"The first thing you need to know is that {_branding['assistant_name']} is always here to help. Just type your question or request naturally.",
        "highlight": "input",
    },
    {
        "step": 2,
        "title": "Modes & Personalities",
        "content": f"{_branding['assistant_name']} has different personalities: helpful (proactive), focus (terse), calm (empathetic). Use `/mode <name>` to switch.",
        "highlight": "mode",
    },
    {
        "step": 3,
        "title": "Cost Tiers",
        "content": "Your system automatically routes queries to the best value tier. But you can override: say 'cheap', 'secret', or 'premium'.",
        "highlight": "tier",
    },
    {
        "step": 4,
        "title": "Secret Mode",
        "content": f"Want unrestricted local AI? Just say 'secret' or 'unrestricted' - {_branding['assistant_name']} will use Ollama locally with no safety filters.",
        "highlight": "secret",
    },
    {
        "step": 5,
        "title": "Memory",
        "content": f"{_branding['assistant_name']} remembers things you tell it with /remember <fact>. Use /memories to list what {_branding['assistant_name']} knows about you.",
        "highlight": "remember",
    },
]


def show_welcome(force: bool = False):
    """Show welcome message on first run"""
    config_path = Path("config/kitty_settings.json")

    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

        onboarding = config.get("features", {}).get("onboarding", {})

        if not force and not onboarding.get("show_welcome", True):
            return

    console.print(
        Panel(WELCOME_MESSAGE, title=f"🐱 Welcome to {_branding['name']}!", border_style="cyan")
    )


def show_guided_tour():
    """Show step-by-step guided tour"""
    for step_info in ONBOARDING_STEPS:
        panel = Panel(
            step_info["content"],
            title=f"Step {step_info['step']}: {step_info['title']}",
            border_style="green",
        )
        console.print(panel)
        input("\nPress Enter to continue... ")


def get_onboarding_status():
    """Get onboarding configuration status"""
    config_path = Path("config/kitty_settings.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)
        return config.get("features", {}).get("onboarding", {})
    return {"enabled": False}


def disable_onboarding():
    """Disable onboarding after user has seen it"""
    config_path = Path("config/kitty_settings.json")
    if config_path.exists():
        with open(config_path) as f:
            config = json.load(f)

        if "features" not in config:
            config["features"] = {}
        if "onboarding" not in config["features"]:
            config["features"]["onboarding"] = {}

        config["features"]["onboarding"]["show_welcome"] = False

        with open(config_path, "w") as f:
            json.dump(config, f, indent=2)


if __name__ == "__main__":
    show_welcome(force=True)
