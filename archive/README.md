# Archive

Historical code only. Do not import. Do not reference in new code.

Live code lives in `gateway/` and `kitty_gateway/`.

## Contents

- `legacy_src/space_kitty/` — original space_kitty module, superseded by `gateway/`
- `legacy_tests/` — tests for the archived module

## Dead scripts in scripts/

The following scripts have broken imports referencing `src.space_kitty.*` (a path that no longer exists) and are not wired into any live gateway code. Kept for historical reference only:

- `scripts/overnight_retry.py` — broken import: `from src.space_kitty.llm_client import call_llm`
- `scripts/context_pack_generator.py` — references `src/space_kitty/SOUL.md` (path no longer exists)
- `scripts/builder_intake.py` — references `src/space_kitty/SOUL.md` (path no longer exists)
- `scripts/kitty_builder.py` — references `src/space_kitty/llm_client.py` as a path string
