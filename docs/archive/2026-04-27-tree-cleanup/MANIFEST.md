# Tree Cleanup Archive - 2026-04-27

## Scope

Reviewed the runnable Kitty checkout at `/Users/jacobbrizinski/Projects/kitty` and the context/manuals folder at `/Users/jacobbrizinski/Documents/Kitty` before archiving anything.

This cleanup pass did not delete source files. It moved standalone benchmark scratch files out of the project root and documented files that should not be archived yet.

## Archive Review

- `/Users/jacobbrizinski/Projects/kitty/skills/legacy-skills/`: no source content found; contains only `.DS_Store`.
- `/Users/jacobbrizinski/Documents/Kitty/backups/`: empty.
- `/Users/jacobbrizinski/Documents/Backups/`: contains `.snbackup` files; no Kitty source/context was identified during this pass.

## Moved Here

| Original path | Archive path | Reason |
| --- | --- | --- |
| `model_loader.py` | `model-benchmark/model_loader_3b.py` | Standalone 3B MLX benchmark loader; not imported by the live app. |
| `model_test_results_20260427_100140.txt` | `model-benchmark/model_test_results_20260427_100140.txt` | Benchmark result file with only the CSV/header evidence from the model test pass. |
| `test_kitty_models.sh` | `model-benchmark/test_kitty_models_3b.sh` | Standalone 3B MLX benchmark script; no live references outside the archive. |
| previously archived `model_loader.py` | `model-benchmark/model_loader.py` | Standalone 8B MLX benchmark loader variant preserved separately from the 3B loader. |
| previously archived `test_kitty_models.sh` | `model-benchmark/test_kitty_models.sh` | Standalone 8B MLX benchmark script variant preserved separately from the 3B script. |

## Why This Was Safe

- The benchmark files were untracked scratch helpers at the project root.
- `rg` found no live imports or references from the app, tests, or frontend after excluding generated/vendor directories.
- The scripts are useful historical benchmark material, so they were archived instead of deleted.

## Do Not Delete Or Archive Yet

- `src/eval/rlhf_collection.py`: tracked deletion exists in the working tree, but `src/api/streaming_routes.py` still imports `PreferenceCollector` from it. Restore or replace that import before accepting the deletion.
- `evals/artifacts/*.json`: append-only eval evidence. Do not bulk-delete without defining retention policy and preserving baseline/regression history.
- `eval_snapshots/`: eval-loop evidence. Keep unless a retention policy replaces it.
- `data/`: runtime state and local databases. Never clean with a broad delete.
- `src/services/context_service.py`: imported by `src/core/specialist_framework.py`.
- `src/core/specialists/registry.py`: imported by `src/core/specialist_framework.py`.
- `kitty-chat/app/components/ActiveNodes.tsx`: imported by `kitty-chat/app/page.tsx`.
- `kitty-chat/next.config.js`: active frontend configuration.

## Legacy Candidates For A Later Pass

These deleted tracked files may be real legacy code, but they should not be finalized as removed until their reusable logic is reviewed and any active references are replaced:

- `src/graphs/__init__.py`
- `src/graphs/hardware_subgraph.py`
- `src/graphs/investigative_subgraph.py`
- `src/graphs/main_graph.py`
- `src/modules/__init__.py`
- `src/modules/kitty_software_analysis.py`
- `src/modules/persona_engine.py`
- `src/modules/prompt_enhancer.py`
- `src/modules/visual_diagram_generator.py`
- `src/modules/test_files/pe32.exe`
- `src/sensory/__init__.py`

## Verification Performed

- Reviewed current and previous archive locations.
- Reviewed deleted tracked files through `git show HEAD:<path>` before classifying them.
- Searched for benchmark references before and after archive movement.
- Reran the project test suite after cleanup.
