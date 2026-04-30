# Known Limitations & Deferred Scope

Date: 2026-04-30

The Kitty release candidate represents a stable, market-ready baseline. To maintain safety, cost controls, and code maintainability, several planned capabilities have been intentionally parked, deferred, or blocked.

## 1. Parked / Deferred Capabilities

The following features have partial concepts or code in the repository but **must not be enabled or built** without a new, explicit spec passing through the Builder Intake process:

- **MCP Agent Bundle:** (KnowledgeGetter, Librarian, VisionGuide, CodeReviewer, Overnighter). These agents exist in the source tree but require extensive safety, routing, and dependency audits before they are allowed into active execution paths.
- **`kitty-system` Physical Split:** The architecture plan outlines separating the control documents from the runnable app. While the preflight (`scripts/plan_workspace_separation.py`) has passed, no physical moves are authorized until an explicit spec is approved.
- **Memory Migration:** Transitioning memory architecture beyond the current validated, focused modules (Vector Store, Inspect/Forget) is blocked.
- **Automated Financial/Budget Analysis:** Touching sensitive financial data (e.g., bank app integrations) is strictly blocked pending a comprehensive Privacy Spec.

## 2. System Limitations

- **Optional Dependency Constraints:** Certain advanced components (e.g., Exa search, Firecrawl scraping, MCP packages) are not actively loaded into the standard execution environment. Attempting to invoke them directly will currently result in `ModuleNotFoundError`.
- **Local Inference Constraints:** The `mlx_lm` package is verified as present, but local inference performance depends strictly on your hardware. If Kitty is run on a machine without enough Apple Silicon memory, local inference tasks may OOM or fail abruptly.
- **`garage-ui` Frontend:** The UI is primarily a diagnostic and developer interface. It lacks deep mobile responsiveness and comprehensive accessibility features. Polishing the UI is currently out of scope.
- **Subprocess Security Enforcement:** The `security_scanner.py` restricts `kittybuilder` from executing high-risk system commands. Some advanced auto-refactoring might fail if it triggers these static regex boundaries.

## 3. Documentation Limits

- The chat log consolidation extraction process is explicitly designed to **avoid** promoting assistant-generated speculation into canon. As a result, certain preferences (like `$129/month` pricing goals) remain unverified "Open Loops."

## Revival Trigger

If any limitation is causing a severe workflow block, refer to `docs/BUILDER_INTAKE.md` to initiate a spec review. No limitation should be removed opportunistically.
