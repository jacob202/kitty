# Config Index

**Status**: 2026-05-09 - Validation added via Pydantic

| File | Purpose | Key Settings |
|------|---------|-------------|
| `kitty_settings.json` | Main app settings | port, debug, model, log_level |
| `hardware_triggers.json` | MLX model routing by hardware | cpu vs GPU triggers |
| `domain_config.json` | Domain routing | domain→specialist mappings |
| `ui_strings.json` | UI text/strings | button labels, messages |
| `patterns.json` | Regex patterns | code, prompts |
| `mlx_optimization.json` | MLX tuning | batch sizes, cache |
| `SOUL.md` | Voice/personality | system prompt, voice settings |

## Validation

Use Pydantic validation:

```python
from src.config.validators import load_settings

settings = load_settings()  # validates on load
```

## Specialist Configs

| File | Specialist |
|------|------------|
| `specialists/code.json` | Code specialist |
| `specialists/research.json` | Research specialist |
| `specialists/creative.json` | Creative specialist |
| `specialists/knowledge_researcher.json` | Knowledge researcher |
| `specialists/automotive.json` | Automotive specialist |
| `specialists/fitness.json` | Fitness specialist |
| `specialists/audio.json` | Audio specialist |
| `specialists/infrastructure.json` | Infrastructure specialist |
| `specialists/design.json` | Design specialist |
| `specialists/soul.json` | Soul/Life specialist |
| `specialists/growth.json` | Growth specialist |
| `specialists/knowledge_acquisition.json` | Knowledge acquisition |

## Usage

Load in code:

```python
from src.config.settings_manager import load_settings

settings = load_settings()  # loads kitty_settings.json
```

Or access other config:

```python
from src.config.config_loader import load_config

hardware = load_config("hardware_triggers")
domain = load_config("domain_config")
```

---

**Last updated**: 2026-05-09