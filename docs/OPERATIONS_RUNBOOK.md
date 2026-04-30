# Operations Runbook

Date: 2026-04-30

This document outlines the standard operational procedures for running, testing, and managing the Kitty personal assistant environment.

## 1. Quick Start

The Kitty environment provides a convenient shell script wrapper for managing the server lifecycle.

### Launching the Application

Start the backend and UI (requires both Python and Node.js environments to be ready):

```bash
./scripts/start.sh
```

Alternatively, use the background launcher if you only need the Python backend:

```bash
./kitty start
```

### Checking Status

Verify whether the backend is running and view its active ports:

```bash
./kitty status
```

### Stopping the Application

To kill the backend:

```bash
./kitty stop
```

## 2. Testing and Validation

All changes to the Kitty workspace must pass the automated gate checks and test suite before being accepted.

### Running Gates (File Governance and Preflight Checks)

The governance scripts check for unwanted structural changes, unknown generated directories, and protected metadata modifications.

```bash
bash scripts/run_gates.sh
```

### Running the Python Test Suite

The comprehensive test suite (currently validating ~342 tests) executes via `pytest`.

```bash
/opt/homebrew/bin/python3.12 -m pytest tests/ -q --tb=short
```

### Running Frontend Tests

The Garage UI contains its own regression test suite using Vitest.

```bash
cd garage-ui
npm run test -- --run
```

## 3. Builder Intake & Task Automation

The Kitty project uses a strict control-layer system. Code changes should not happen opportunistically. 

1. Write or verify a spec in `specs/`.
2. Add tasks via `docs/BUILDER_INTAKE.md` or `intake/`.
3. A builder worker must operate within the boundaries of the spec (allowed files, forbidden files).
4. Run `kittybuilder` with explicit limits:
   ```bash
   /opt/homebrew/bin/python3.12 scripts/kitty_builder.py --project . --spec specs/your-spec.spec.md
   ```
   *(Note: Builder write paths may be blocked depending on active security enforcement gates.)*

## 4. Known Limits & Deferred Scope

Do not attempt to enable or fix these features without referring to `docs/KNOWN_LIMITATIONS.md` and writing an explicit new spec:

- MCP Agent bundles (parked in dirty tree)
- Physical `kitty-system/kitty-app` repo splitting
- Uncontrolled LLM fine-tuning or memory migration outside focused modules
