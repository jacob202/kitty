# Gates

Last updated: 2026-04-28

Gates are validation commands that prove a bounded change stayed inside the approved lane.

## Current Control-Layer Gates

Run these after editing builder intake or file-governance tooling:

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/test_builder_intake.py tests/test_file_governance.py tests/test_context_pack_generator.py tests/test_kitty_builder.py -q --tb=short
/opt/homebrew/bin/python3.12 -m py_compile scripts/builder_intake.py scripts/check_file_governance.py scripts/context_pack_generator.py scripts/kitty_builder.py
python3 scripts/check_file_governance.py --dry-run
python3 scripts/context_pack_generator.py --project . --out .cache/kitty_context_pack.md
bash scripts/run_gates.sh
```

## Gate Rules

- Run only the gate that matches the touched surface unless a spec requires more.
- Do not claim completion without fresh gate output.
- A dry-run gate may list cleanup candidates; it must not delete, move, archive, or rewrite files.
- Runtime, memory, UI, and data gates require their own approved specs before this control layer touches those areas.

## Future Full Gate

`scripts/run_gates.sh` should eventually include secrets checks, correction enforcement, storage routing checks, frontend linting, file governance, Python compilation, and pytest. Until those scripts exist, the full gate must not pretend to validate surfaces it cannot actually check.
