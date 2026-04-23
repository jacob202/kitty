import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import appdirs

logger = logging.getLogger(__name__)

@dataclass
class ComponentRules:
    designator_pattern: str = r"^[A-Z]{1,3}\d+$"
    value_pattern: str = r"^[\d.]+[kμm]?[ΩFHAV]?$"
    min_confidence: float = 0.3
    require_units: bool = False

class ConfigManager:
    """Centralized configuration management for hardware analysis."""

    def __init__(self, app_name: str = "AgentCompany"):
        self.app_name = app_name
        self.config_dirs = self._get_config_search_paths()
        self._cache = {}

    def _get_config_search_paths(self) -> list[Path]:
        """Get ordered list of config search paths."""
        return [
            Path.cwd() / "config",
            Path.home() / f".config/{self.app_name}",
            Path(appdirs.user_config_dir(self.app_name)),
            Path(__file__).parent.parent / "config"  # Project defaults
        ]

    def _find_config(self, name: str) -> Path | None:
        """Locate config file in search paths."""
        for config_dir in self.config_dirs:
            config_path = config_dir / f"{name}.json"
            if config_path.exists():
                return config_path
        return None

    def load_config(self, name: str, use_cache: bool = True, validate: bool = True, diff: bool = False) -> dict[str, Any]:
        """Load config with version checking and schema validation."""
        if use_cache and name in self._cache:
            return self._cache[name]

        config_path = self._find_config(name)
        if not config_path:
            raise FileNotFoundError(f"Config '{name}' not found in: {[str(p) for p in self.config_dirs]}")

        try:
            with open(config_path) as f:
                config = json.load(f)

                # Version check
                current_version = config.get("schema_version", 1)
                if current_version > 1:
                    logger.warning(f"Config {name} uses schema v{current_version} (expected v1)")

                # Schema validation
                if validate:
                    if name == "electronics":
                        self._validate_electronics_config(config)
                    elif name == "models":
                        self._validate_model_config(config)

                # Environment variable expansion
                config = self._expand_env_vars(config)

                if diff and name in self._cache:
                    from deepdiff import DeepDiff
                    diff = DeepDiff(self._cache[name], config, ignore_order=True)
                    if diff:
                        logger.info(f"Config {name} changed:\n{diff.pretty()}")

                self._cache[name] = config
                return config
        except Exception as e:
            logger.error(f"Failed loading config {name}: {str(e)}")
            raise

    def get_component_rules(self) -> ComponentRules:
        """Get validated component validation rules."""
        try:
            config = self.load_config("electronics")
            return ComponentRules(
                designator_pattern=config.get("designator_pattern"),
                value_pattern=config.get("value_pattern"),
                min_confidence=float(config.get("min_confidence", 0.3)),
                require_units=bool(config.get("require_units", False))
            )
        except Exception as e:
            logger.warning(f"Using default component rules: {str(e)}")
            return ComponentRules()

# Global instance for easy access
config_manager = ConfigManager()
