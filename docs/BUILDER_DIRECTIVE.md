# Builder Directive

Last updated: 2026-04-28

Kitty Builder is not part of normal Kitty runtime startup. It is a controlled workbench tool.

## Required Invocation

```bash
./kittybuilder --project /Users/jacobbrizinski/Projects/kitty-system/kitty-app --spec specs/example.spec.md
./kittybuilder --project /Users/jacobbrizinski/Projects/kitty-system/kitty-app --spec specs/example.spec.md --execute
```

Rules:

- `--project` is required.
- `--spec` is required.
- Dry-run is the default.
- `--execute` is required before any future write-capable builder path.
- The spec must live inside the project.
- The legacy interactive builder must not auto-launch from runtime Kitty.
- Builder writes and command execution are gated by `src/utils/security_scanner.py`.
- Scanner findings block the builder action before file writes or subprocess launch.

## Completion Report

Every builder task must report:

- files read
- files changed
- commands run
- tests passed/failed
- gates passed/failed
- docs updated
- known risks
- next smallest action
