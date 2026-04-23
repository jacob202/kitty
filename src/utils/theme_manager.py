"""
Theme Manager - Dark/Light mode and theme customization
"""

import json
from pathlib import Path

from rich.console import Console

console = Console()

THEMES = {
    "light": {
        "name": "Light",
        "background": "#FFFFFF",
        "foreground": "#000000",
        "accent": "#007AFF",
        "success": "#34C759",
        "warning": "#FF9500",
        "error": "#FF3B30",
        "border_style": "cyan",
    },
    "dark": {
        "name": "Dark",
        "background": "#1E1E1E",
        "foreground": "#FFFFFF",
        "accent": "#0A84FF",
        "success": "#30D158",
        "warning": "#FF9F0A",
        "error": "#FF453A",
        "border_style": "blue",
    },
    "hardware": {
        "name": "Hardware",
        "background": "#0D1117",
        "foreground": "#C9D1D9",
        "accent": "#58A6FF",
        "success": "#3FB950",
        "warning": "#D29922",
        "error": "#F85149",
        "border_style": "cyan",
    },
    "matrix": {
        "name": "Matrix",
        "background": "#000000",
        "foreground": "#00FF00",
        "accent": "#00FF00",
        "success": "#00FF00",
        "warning": "#FFFF00",
        "error": "#FF0000",
        "border_style": "green",
    },
    "sunset": {
        "name": "Sunset",
        "background": "#1A0A0A",
        "foreground": "#FFD4D4",
        "accent": "#FF6B6B",
        "success": "#4ECDC4",
        "warning": "#FFE66D",
        "error": "#FF6B6B",
        "border_style": "red",
    },
    "ocean": {
        "name": "Ocean",
        "background": "#0A1929",
        "foreground": "#E6F1FF",
        "accent": "#64FFDA",
        "success": "#4ECDC4",
        "warning": "#FFD93D",
        "error": "#FF6B6B",
        "border_style": "cyan",
    },
}

CUSTOM_THEMES_PATH = Path("config/custom_themes.json")


class ThemeManager:
    def __init__(self):
        self.current_theme = "hardware"
        self.theme_mode = "auto"
        self._load_settings()

    def _load_settings(self):
        """Load theme settings from config"""
        config_path = Path("config/kitty_settings.json")
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            ui = config.get("ui", {})
            self.current_theme = ui.get("default_theme", "hardware")
            self.theme_mode = ui.get("theme_mode", "auto")

    def _save_settings(self):
        """Save theme settings to config"""
        config_path = Path("config/kitty_settings.json")
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)

            if "ui" not in config:
                config["ui"] = {}
            config["ui"]["default_theme"] = self.current_theme
            config["ui"]["theme_mode"] = self.theme_mode

            with open(config_path, "w") as f:
                json.dump(config, f, indent=2)

    def get_theme(self, name: str | None = None) -> dict:
        """Get theme by name"""
        theme_name = name or self.current_theme

        # Check custom themes first
        if CUSTOM_THEMES_PATH.exists():
            with open(CUSTOM_THEMES_PATH) as f:
                custom = json.load(f)
            if theme_name in custom:
                return custom[theme_name]

        return THEMES.get(theme_name, THEMES["hardware"])

    def list_themes(self) -> list:
        """List all available themes"""
        themes = list(THEMES.keys())
        if CUSTOM_THEMES_PATH.exists():
            with open(CUSTOM_THEMES_PATH) as f:
                custom = json.load(f)
            themes.extend(list(custom.keys()))
        return themes

    def set_theme(self, name: str):
        """Set current theme"""
        if name in THEMES or (
            CUSTOM_THEMES_PATH.exists() and name in json.load(open(CUSTOM_THEMES_PATH))
        ):
            self.current_theme = name
            self._save_settings()
            return True
        return False

    def set_mode(self, mode: str):
        """Set theme mode: auto, dark, light"""
        if mode in ["auto", "dark", "light"]:
            self.theme_mode = mode

            # Auto-switch based on system preference
            if mode == "auto":
                # Check system dark mode (macOS)
                import subprocess

                try:
                    result = subprocess.run(
                        ["defaults", "read", "-g", "AppleInterfaceStyle"],
                        capture_output=True,
                        text=True,
                    )
                    if "Dark" in result.stdout:
                        self.set_theme("dark")
                    else:
                        self.set_theme("light")
                except Exception:
                    self.set_theme("hardware")
            elif mode == "dark":
                self.set_theme("dark")
            elif mode == "light":
                self.set_theme("light")

            self._save_settings()
            return True
        return False

    def create_custom_theme(self, name: str, colors: dict):
        """Create a custom theme"""
        custom = {}
        if CUSTOM_THEMES_PATH.exists():
            with open(CUSTOM_THEMES_PATH) as f:
                custom = json.load(f)

        custom[name] = colors

        with open(CUSTOM_THEMES_PATH, "w") as f:
            json.dump(custom, f, indent=2)

        return True

    def get_rich_styles(self) -> dict:
        """Get Rich styles for current theme"""
        theme = self.get_theme()
        return {"console": theme, "panel_border": theme.get("border_style", "cyan")}


def list_available_themes():
    """List all themes with descriptions"""
    print("\n🎨 Available Themes:")
    print("-" * 40)
    for name, theme in THEMES.items():
        print(f"  {name:12} - {theme['name']}")
    print("-" * 40)
    print("\nTo switch themes, say:")
    print('  "use dark mode" or "switch to ocean theme"')
    print("  Or use /theme <name>")


def toggle_dark_mode():
    """Toggle between dark and light mode"""
    manager = ThemeManager()
    if manager.theme_mode == "dark":
        manager.set_mode("light")
        console.print("☀️ Switched to Light Mode")
    else:
        manager.set_mode("dark")
        console.print("🌙 Switched to Dark Mode")


if __name__ == "__main__":
    manager = ThemeManager()
    print(f"Current theme: {manager.current_theme}")
    print(f"Theme mode: {manager.theme_mode}")
    list_available_themes()
