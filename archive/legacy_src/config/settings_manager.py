#!/usr/bin/env python3
"""
Kitty AI Settings Manager
Centralized configuration management for profiles, model settings, and preferences.
"""

import copy
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Model configuration settings."""

    provider: str = "claude"  # claude, openai, ollama
    model_name: str = "claude-3-5-sonnet"
    temperature: float = 0.7
    max_tokens: int = 4000
    top_p: float = 1.0
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0
    timeout: int = 120


@dataclass
class ToolAvailability:
    """Which tools are enabled for this profile."""

    web_search: bool = True
    code_execution: bool = False
    file_operations: bool = True
    schematic_analysis: bool = True
    bom_manager: bool = True
    datasheet_lookup: bool = True
    vision_analysis: bool = True
    vector_search: bool = True
    memory_recall: bool = True
    custom_agents: bool = True


@dataclass
class MiddlewareSettings:
    """Middleware routing and cost control settings."""

    auto_route: bool = True
    cost_threshold_local: float = 0.0  # Always use local below this
    cost_threshold_flash: float = 0.01  # Use flash below this
    cost_threshold_heavy: float = 0.05  # Use heavy below this
    prefer_local_for_simple: bool = True
    prefer_flash_for_vision: bool = True
    prefer_heavy_for_coding: bool = True
    max_cost_per_request: float = 0.10


@dataclass
class ProfileSettings:
    """Complete profile configuration."""

    name: str = "default"
    description: str = "Default Kitty profile"
    version: str = "1.0"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Core model settings
    model: ModelConfig = field(default_factory=ModelConfig)

    # System prompt/personality
    system_prompt: str = "You are Kitty, an AI assistant."
    personality: str = "helpful"
    thinking_style: str = "step-by-step"  # step-by-step, direct, creative
    response_format: str = "verbose"  # concise, verbose, structured

    # Tool availability
    tools: ToolAvailability = field(default_factory=ToolAvailability)

    # Middleware settings
    middleware: MiddlewareSettings = field(default_factory=MiddlewareSettings)

    # UI preferences
    ui_theme: str = "hardware"
    animation_speed: str = "normal"
    compact_mode: bool = False

    # Feature flags
    features: dict[str, Any] = field(default_factory=dict)


class SettingsManager:
    """
    Centralized settings management for Kitty AI profiles.
    Handles loading, saving, and switching between configuration profiles.
    """

    DEFAULT_PROFILES = [
        "research_reasoning",
        "analytical_precise",
        "creative_innovative",
        "repair_technician",
        "code_developer",
        "teacher_educator",
        "balanced",
    ]

    def __init__(self, config_dir: str | None = None):
        """
        Initialize the SettingsManager.

        Args:
            config_dir: Directory for storing profiles. Defaults to src/config/profiles
        """
        if config_dir:
            self.config_dir = Path(config_dir)
        else:
            # Determine project root
            current_file = Path(__file__).resolve()
            project_root = current_file.parent.parent.parent
            self.config_dir = project_root / "src" / "config" / "profiles"

        self.config_dir.mkdir(parents=True, exist_ok=True)

        # State file tracks active profile
        self.state_file = self.config_dir / ".active_profile"

        # Cache for loaded profiles
        self._profile_cache: dict[str, ProfileSettings] = {}
        self._active_profile: str | None = None

        # Initialize default profiles if they don't exist
        self._initialize_default_profiles()

        # Load active profile
        self._load_active_profile()

    def _initialize_default_profiles(self):
        """Create default profiles if they don't exist."""
        for profile_name in self.DEFAULT_PROFILES:
            profile_path = self.config_dir / f"{profile_name}.json"
            if not profile_path.exists():
                self._create_default_profile(profile_name)

    def _create_default_profile(self, profile_name: str):
        """Create a built-in default profile."""
        profiles_dir = Path(__file__).parent / "profiles"
        template_path = profiles_dir / f"{profile_name}.json"

        if template_path.exists():
            # Copy from template
            import shutil

            shutil.copy(template_path, self.config_dir / f"{profile_name}.json")
        else:
            # Create generic profile
            profile = self._get_builtin_profile_config(profile_name)
            self.save_profile(profile_name, profile)

    def _get_builtin_profile_config(self, profile_name: str) -> ProfileSettings:
        """Get built-in configuration for a profile."""
        configs = {
            "research_reasoning": ProfileSettings(
                name="research_reasoning",
                description="Deep analysis and thorough investigation",
                model=ModelConfig(
                    provider="claude",
                    model_name="claude-3-5-sonnet",
                    temperature=0.3,
                    max_tokens=8000,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1,
                ),
                system_prompt=(
                    "You are a research assistant specializing in thorough investigation. "
                    "Approach every query with academic rigor. Cite sources when possible. "
                    "Provide comprehensive analysis with multiple perspectives. "
                    "Always verify facts and note uncertainties."
                ),
                personality="analytical",
                thinking_style="step-by-step",
                response_format="structured",
                tools=ToolAvailability(
                    web_search=True,
                    code_execution=False,
                    file_operations=True,
                    schematic_analysis=False,
                    bom_manager=False,
                    datasheet_lookup=True,
                    vision_analysis=False,
                    vector_search=True,
                    memory_recall=True,
                    custom_agents=True,
                ),
                middleware=MiddlewareSettings(
                    auto_route=True, prefer_heavy_for_coding=True, max_cost_per_request=0.15
                ),
                features={
                    "deep_research": True,
                    "source_verification": True,
                    "multi_step_analysis": True,
                },
            ),
            "analytical_precise": ProfileSettings(
                name="analytical_precise",
                description="Exact, technical, detail-oriented responses",
                model=ModelConfig(
                    provider="claude",
                    model_name="claude-3-5-sonnet",
                    temperature=0.1,
                    max_tokens=4000,
                    top_p=0.95,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                ),
                system_prompt=(
                    "You are a precise technical assistant. Provide exact, accurate information. "
                    "Use precise terminology and avoid ambiguity. Include specific measurements, "
                    "values, and units. If uncertain, say so explicitly. Focus on correctness "
                    "over speed."
                ),
                personality="precise",
                thinking_style="direct",
                response_format="structured",
                tools=ToolAvailability(
                    web_search=True,
                    code_execution=True,
                    file_operations=True,
                    schematic_analysis=True,
                    bom_manager=True,
                    datasheet_lookup=True,
                    vision_analysis=True,
                    vector_search=True,
                    memory_recall=True,
                    custom_agents=False,
                ),
                middleware=MiddlewareSettings(
                    auto_route=True, prefer_heavy_for_coding=True, max_cost_per_request=0.08
                ),
                features={
                    "strict_validation": True,
                    "unit_awareness": True,
                    "precision_focus": True,
                },
            ),
            "creative_innovative": ProfileSettings(
                name="creative_innovative",
                description="Out-of-the-box thinking and brainstorming",
                model=ModelConfig(
                    provider="openai",
                    model_name="gpt-4o",
                    temperature=1.2,
                    max_tokens=4000,
                    top_p=0.95,
                    frequency_penalty=0.3,
                    presence_penalty=0.3,
                ),
                system_prompt=(
                    "You are a creative thinking partner. Generate novel ideas and approaches. "
                    "Think laterally and make unexpected connections. Encourage brainstorming "
                    "and exploration. Challenge assumptions. Be enthusiastic and inspiring."
                ),
                personality="creative",
                thinking_style="creative",
                response_format="verbose",
                tools=ToolAvailability(
                    web_search=True,
                    code_execution=False,
                    file_operations=True,
                    schematic_analysis=False,
                    bom_manager=False,
                    datasheet_lookup=False,
                    vision_analysis=False,
                    vector_search=True,
                    memory_recall=True,
                    custom_agents=True,
                ),
                middleware=MiddlewareSettings(auto_route=True, max_cost_per_request=0.10),
                features={
                    "brainstorm_mode": True,
                    "divergent_thinking": True,
                    "idea_generation": True,
                },
            ),
            "repair_technician": ProfileSettings(
                name="repair_technician",
                description="Electronics repair focused - default for Kitty",
                model=ModelConfig(
                    provider="claude",
                    model_name="claude-3-5-sonnet",
                    temperature=0.4,
                    max_tokens=4000,
                    top_p=0.95,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                ),
                system_prompt=(
                    "You are Kitty, an expert electronics repair technician specializing in "
                    "vintage audio equipment. You prioritize safety first - always mention "
                    "discharge procedures and high-voltage warnings. Use exact component "
                    "designators (e.g., C05, R123). Reference schematics accurately. Be "
                    "methodical in diagnostics. Consider thermal issues, capacitor aging, "
                    "and common failure modes. When uncertain, ask for measurements."
                ),
                personality="technician",
                thinking_style="step-by-step",
                response_format="structured",
                tools=ToolAvailability(
                    web_search=True,
                    code_execution=False,
                    file_operations=True,
                    schematic_analysis=True,
                    bom_manager=True,
                    datasheet_lookup=True,
                    vision_analysis=True,
                    vector_search=True,
                    memory_recall=True,
                    custom_agents=True,
                ),
                middleware=MiddlewareSettings(
                    auto_route=True,
                    prefer_local_for_simple=True,
                    prefer_flash_for_vision=True,
                    max_cost_per_request=0.08,
                ),
                features={
                    "safety_first": True,
                    "schematic_integration": True,
                    "component_tracing": True,
                    "vintage_audio_focus": True,
                },
            ),
            "code_developer": ProfileSettings(
                name="code_developer",
                description="Programming and software development",
                model=ModelConfig(
                    provider="claude",
                    model_name="claude-3-5-sonnet",
                    temperature=0.2,
                    max_tokens=8000,
                    top_p=0.95,
                    frequency_penalty=0.0,
                    presence_penalty=0.0,
                ),
                system_prompt=(
                    "You are an expert software developer. Write clean, maintainable code. "
                    "Include type hints, docstrings, and error handling. Follow best practices "
                    "and design patterns. Explain complex logic. Consider edge cases and "
                    "performance. Prefer explicit over implicit. Write tests when appropriate."
                ),
                personality="developer",
                thinking_style="step-by-step",
                response_format="structured",
                tools=ToolAvailability(
                    web_search=True,
                    code_execution=True,
                    file_operations=True,
                    schematic_analysis=False,
                    bom_manager=False,
                    datasheet_lookup=False,
                    vision_analysis=False,
                    vector_search=True,
                    memory_recall=True,
                    custom_agents=True,
                ),
                middleware=MiddlewareSettings(
                    auto_route=True, prefer_heavy_for_coding=True, max_cost_per_request=0.12
                ),
                features={
                    "syntax_highlighting": True,
                    "test_generation": True,
                    "code_review_mode": True,
                    "documentation_focus": True,
                },
            ),
            "teacher_educator": ProfileSettings(
                name="teacher_educator",
                description="Educational explanations and step-by-step guidance",
                model=ModelConfig(
                    provider="claude",
                    model_name="claude-3-5-sonnet",
                    temperature=0.6,
                    max_tokens=4000,
                    top_p=0.9,
                    frequency_penalty=0.1,
                    presence_penalty=0.1,
                ),
                system_prompt=(
                    "You are a patient and knowledgeable teacher. Explain concepts clearly "
                    "using simple language. Build from fundamentals to complexity. Use "
                    "analogies and examples. Check for understanding. Encourage questions. "
                    "Adapt explanations to the learner's level. Celebrate progress."
                ),
                personality="teacher",
                thinking_style="step-by-step",
                response_format="verbose",
                tools=ToolAvailability(
                    web_search=True,
                    code_execution=False,
                    file_operations=True,
                    schematic_analysis=False,
                    bom_manager=False,
                    datasheet_lookup=True,
                    vision_analysis=False,
                    vector_search=True,
                    memory_recall=True,
                    custom_agents=False,
                ),
                middleware=MiddlewareSettings(
                    auto_route=True, prefer_local_for_simple=True, max_cost_per_request=0.06
                ),
                features={
                    "socratic_method": True,
                    "progressive_disclosure": True,
                    "knowledge_checkpoints": True,
                    "example_rich": True,
                },
            ),
        }

        return configs.get(profile_name, ProfileSettings(name=profile_name))

    def _load_active_profile(self):
        """Load the currently active profile from state file."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    state = json.load(f)
                    self._active_profile = state.get("active_profile", "repair_technician")
            except Exception as e:
                logger.error(f"Failed to load active profile: {e}")
                self._active_profile = "repair_technician"
        else:
            # Default to repair_technician (Kitty's default)
            self._active_profile = "repair_technician"
            self._save_active_profile()

    def _save_active_profile(self):
        """Save the active profile to state file."""
        try:
            with open(self.state_file, "w") as f:
                json.dump({"active_profile": self._active_profile}, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save active profile: {e}")

    def list_profiles(self) -> list[dict[str, str]]:
        """
        List all available profiles with their descriptions.

        Returns:
            List of profile info dicts with name, description, and active status
        """
        profiles = []

        for profile_file in sorted(self.config_dir.glob("*.json")):
            if profile_file.name.startswith("."):
                continue

            try:
                with open(profile_file) as f:
                    data = json.load(f)
                    profiles.append(
                        {
                            "name": data.get("name", profile_file.stem),
                            "description": data.get("description", "No description"),
                            "active": data.get("name", profile_file.stem) == self._active_profile,
                        }
                    )
            except Exception as e:
                logger.warning(f"Failed to load profile {profile_file}: {e}")

        return profiles

    def load_profile(self, profile_name: str) -> ProfileSettings:
        """
        Load a profile by name.

        Args:
            profile_name: Name of the profile to load

        Returns:
            ProfileSettings object

        Raises:
            FileNotFoundError: If profile doesn't exist
        """
        # Check cache first
        if profile_name in self._profile_cache:
            return self._profile_cache[profile_name]

        profile_path = self.config_dir / f"{profile_name}.json"

        if not profile_path.exists():
            # Try to create from built-in
            if profile_name in self.DEFAULT_PROFILES:
                self._create_default_profile(profile_name)
            else:
                raise FileNotFoundError(f"Profile '{profile_name}' not found")

        try:
            with open(profile_path) as f:
                data = json.load(f)

            # Parse into dataclass
            profile = self._dict_to_profile(data)
            self._profile_cache[profile_name] = profile
            return profile

        except Exception as e:
            logger.error(f"Failed to load profile {profile_name}: {e}")
            raise

    def _dict_to_profile(self, data: dict[str, Any]) -> ProfileSettings:
        """Convert dict to ProfileSettings dataclass."""
        # Handle nested dataclasses
        model_config = ModelConfig(**data.get("model", {}))
        tools = ToolAvailability(**data.get("tools", {}))
        middleware = MiddlewareSettings(**data.get("middleware", {}))

        # Create profile with parsed nested objects
        profile_data = {k: v for k, v in data.items() if k not in ("model", "tools", "middleware")}
        profile_data["model"] = model_config
        profile_data["tools"] = tools
        profile_data["middleware"] = middleware

        return ProfileSettings(**profile_data)

    def save_profile(self, profile_name: str, profile: ProfileSettings) -> bool:
        """
        Save a profile to disk.

        Args:
            profile_name: Name to save the profile as
            profile: ProfileSettings object to save

        Returns:
            True if successful
        """
        try:
            profile_path = self.config_dir / f"{profile_name}.json"

            # Update timestamps
            profile.name = profile_name
            profile.updated_at = datetime.now().isoformat()

            # Convert to dict
            data = self._profile_to_dict(profile)

            with open(profile_path, "w") as f:
                json.dump(data, f, indent=2)

            # Update cache
            self._profile_cache[profile_name] = profile

            return True

        except Exception as e:
            logger.error(f"Failed to save profile {profile_name}: {e}")
            return False

    def _profile_to_dict(self, profile: ProfileSettings) -> dict[str, Any]:
        """Convert ProfileSettings to dict for serialization."""
        data = {
            "name": profile.name,
            "description": profile.description,
            "version": profile.version,
            "created_at": profile.created_at,
            "updated_at": profile.updated_at,
            "model": asdict(profile.model),
            "system_prompt": profile.system_prompt,
            "personality": profile.personality,
            "thinking_style": profile.thinking_style,
            "response_format": profile.response_format,
            "tools": asdict(profile.tools),
            "middleware": asdict(profile.middleware),
            "ui_theme": profile.ui_theme,
            "animation_speed": profile.animation_speed,
            "compact_mode": profile.compact_mode,
            "features": profile.features,
        }
        return data

    def get_active_profile(self) -> ProfileSettings:
        """
        Get the currently active profile.

        Returns:
            ProfileSettings object for active profile
        """
        return self.load_profile(self._active_profile)

    def set_active_profile(self, profile_name: str) -> bool:
        """
        Set the active profile.

        Args:
            profile_name: Name of profile to activate

        Returns:
            True if successful
        """
        try:
            # Verify profile exists
            self.load_profile(profile_name)

            self._active_profile = profile_name
            self._save_active_profile()

            logger.info(f"Activated profile: {profile_name}")
            return True

        except FileNotFoundError:
            logger.error(f"Cannot activate non-existent profile: {profile_name}")
            return False
        except Exception as e:
            logger.error(f"Failed to activate profile {profile_name}: {e}")
            return False

    def create_profile(
        self, profile_name: str, base_profile: str | None = None
    ) -> ProfileSettings:
        """
        Create a new profile, optionally based on an existing one.

        Args:
            profile_name: Name for the new profile
            base_profile: Optional existing profile to copy from

        Returns:
            New ProfileSettings object
        """
        if base_profile:
            base = self.load_profile(base_profile)
            new_profile = copy.deepcopy(base)
            new_profile.name = profile_name
            new_profile.description = f"Custom profile based on {base_profile}"
            new_profile.created_at = datetime.now().isoformat()
            new_profile.updated_at = datetime.now().isoformat()
        else:
            new_profile = ProfileSettings(
                name=profile_name, description=f"Custom profile: {profile_name}"
            )

        self.save_profile(profile_name, new_profile)
        return new_profile

    def delete_profile(self, profile_name: str) -> bool:
        """
        Delete a profile.

        Args:
            profile_name: Name of profile to delete

        Returns:
            True if successful
        """
        if profile_name in self.DEFAULT_PROFILES:
            logger.warning(f"Cannot delete built-in profile: {profile_name}")
            return False

        profile_path = self.config_dir / f"{profile_name}.json"

        try:
            if profile_path.exists():
                profile_path.unlink()

            # Remove from cache
            if profile_name in self._profile_cache:
                del self._profile_cache[profile_name]

            # If this was the active profile, switch to default
            if self._active_profile == profile_name:
                self.set_active_profile("repair_technician")

            return True

        except Exception as e:
            logger.error(f"Failed to delete profile {profile_name}: {e}")
            return False

    def reset_to_defaults(self) -> bool:
        """
        Reset all profiles to their default configurations.

        Returns:
            True if successful
        """
        try:
            # Clear cache
            self._profile_cache.clear()

            # Delete all profile files except state
            for profile_file in self.config_dir.glob("*.json"):
                if not profile_file.name.startswith("."):
                    profile_file.unlink()

            # Recreate default profiles
            self._initialize_default_profiles()

            # Reset to repair_technician
            self.set_active_profile("repair_technician")

            logger.info("Reset all profiles to defaults")
            return True

        except Exception as e:
            logger.error(f"Failed to reset profiles: {e}")
            return False

    def update_profile_field(self, profile_name: str, field_path: str, value: Any) -> bool:
        """
        Update a specific field in a profile using dot notation.

        Args:
            profile_name: Profile to update
            field_path: Dot-notation path (e.g., "model.temperature")
            value: New value

        Returns:
            True if successful
        """
        try:
            profile = self.load_profile(profile_name)

            # Navigate to the field
            parts = field_path.split(".")
            target = profile

            for part in parts[:-1]:
                target = getattr(target, part)

            # Set the value
            setattr(target, parts[-1], value)

            # Save
            return self.save_profile(profile_name, profile)

        except Exception as e:
            logger.error(f"Failed to update {field_path} in {profile_name}: {e}")
            return False

    def export_profile(self, profile_name: str, export_path: str) -> bool:
        """
        Export a profile to a file.

        Args:
            profile_name: Profile to export
            export_path: Path to export to

        Returns:
            True if successful
        """
        try:
            profile = self.load_profile(profile_name)
            data = self._profile_to_dict(profile)

            with open(export_path, "w") as f:
                json.dump(data, f, indent=2)

            return True

        except Exception as e:
            logger.error(f"Failed to export profile {profile_name}: {e}")
            return False

    def import_profile(self, import_path: str, profile_name: str | None = None) -> str | None:
        """
        Import a profile from a file.

        Args:
            import_path: Path to import from
            profile_name: Optional new name for the profile

        Returns:
            Name of imported profile, or None if failed
        """
        try:
            with open(import_path) as f:
                data = json.load(f)

            # Use provided name or from file
            name = profile_name or data.get("name", "imported_profile")

            # Parse and save
            profile = self._dict_to_profile(data)
            profile.name = name

            if self.save_profile(name, profile):
                return name
            return None

        except Exception as e:
            logger.error(f"Failed to import profile from {import_path}: {e}")
            return None

    def get_profile_summary(self, profile_name: str) -> dict[str, Any]:
        """
        Get a summary of a profile for display.

        Args:
            profile_name: Profile to summarize

        Returns:
            Dict with profile summary
        """
        try:
            profile = self.load_profile(profile_name)

            return {
                "name": profile.name,
                "description": profile.description,
                "active": profile_name == self._active_profile,
                "model": {
                    "provider": profile.model.provider,
                    "model_name": profile.model.model_name,
                    "temperature": profile.model.temperature,
                    "max_tokens": profile.model.max_tokens,
                },
                "personality": profile.personality,
                "thinking_style": profile.thinking_style,
                "response_format": profile.response_format,
                "tools_enabled": sum(
                    [
                        profile.tools.web_search,
                        profile.tools.code_execution,
                        profile.tools.file_operations,
                        profile.tools.schematic_analysis,
                        profile.tools.bom_manager,
                        profile.tools.datasheet_lookup,
                        profile.tools.vision_analysis,
                        profile.tools.vector_search,
                        profile.tools.memory_recall,
                        profile.tools.custom_agents,
                    ]
                ),
            }

        except Exception as e:
            logger.error(f"Failed to get summary for {profile_name}: {e}")
            return {}


# Global instance for easy access
settings_manager = SettingsManager()


if __name__ == "__main__":
    # Test the settings manager
    sm = SettingsManager()

    print("Available profiles:")
    for profile in sm.list_profiles():
        active_marker = " [ACTIVE]" if profile["active"] else ""
        print(f"  - {profile['name']}: {profile['description']}{active_marker}")

    print("\nActive profile details:")
    active = sm.get_active_profile()
    print(f"  Name: {active.name}")
    print(f"  Model: {active.model.model_name}")
    print(f"  Temperature: {active.model.temperature}")
    print(f"  Personality: {active.personality}")
