# Kitty documentation

Last updated: **2026-05-13**

## Read first (authority)

When instructions conflict:

1. Jacob’s latest message  
2. **`AGENTS.md`**  
3. **`CLAUDE.md`** (or tool-specific stub)  
4. **`docs/LAYER0_CONTROL_PLANE.md`**  
5. **`docs/STANDUP.md`**  
6. **`docs/ARCHITECTURE.md`** — live stack, ports, gateways  
7. **`CURRENT_FOCUS.md`** · **`TASKS.md`** · **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`**  
8. **`docs/DECISIONS.md`**  
9. Approved spec for the task (`specs/`)  
10. **`docs/AGENT_COORDINATION.md`** — **only** when coordinating lanes (long file)

---

## Canonical repo

**Runnable checkout:** `/Users/jacobbrizinski/Projects/kitty`  
Legacy paths (`kitty-system`, Desktop copies) are **historical** unless a new **DECISIONS** entry reopens them.

---

## Single source of truth by category

| Category | Canonical file | Notes |
|----------|----------------|-------|
| Orientation + hook block | **`docs/STANDUP.md`** | Emotional + operational “where we are” |
| Stack / ports / services | **`docs/ARCHITECTURE.md`** | Taken from `kitty_gateway/*.sh` values when possible |
| Feature roadmap + phases | **`docs/UNIFIED_IMPLEMENTATION_PLAN.md`** | Execution spine; **`TASKS.md`** = thin checklist |
| Session compact / handoff ritual | **`docs/HANDOFF_AND_COMPACT.md`** | Replaces old **SESSION_COMPACT** + **CURSOR_COMPACT** splits |
| Live handoff scratchpad | **`SESSION_HANDOFF.md`** (root) | Refresh before compact / new thread |
| Workflows + engineering loop | **`docs/PROCESS_UPGRADES.md`** | Replaces root **ENGINEERING_LOOP.md** |
| Storage routing | **`docs/DATA_ROUTING.md`** | With **`AGENTS.md`** storage table |
| Durable decisions | **`docs/DECISIONS.md`** | |
| Deferred ideas | **`docs/PARKED_FEATURES.md`** | |
| Open questions | **`docs/OPEN_LOOPS.md`** | |
| File / lane boundaries | **`docs/FILE_GOVERNANCE.md`** | |
| Improvement scores / audit | **`docs/IMPROVEMENT_AUDIT.md`** | |
| Historical artifacts | **`docs/archive/`** | Merge gates, old handoffs, retired audits |
| Inventories & reports | **`docs/audits/`** | Point-in-time |
| Specs | **`specs/`** | Approved implementation units |

**Do not** resurrect parallel “index” or “manifest” files at repo root — retired **MASTER_INDEX**, **KITTY_CONTEXT**, **PROJECT_REALITY_CHECK**, **FILE_MANIFEST**, **MEMORY_INDEX**.

---

## Nested planning dirs

- **`docs/plans/`**, **`docs/superpowers/plans/`** — dated drafts; verify against **UNIFIED** plan + **DECISIONS** before building.  
- **`docs/superpowers/plans/`** also has a **`README.md`** noting legacy phase files.

---

## Stale-doc rule

If a document says the runnable app lives **outside** `/Users/jacobbrizinski/Projects/kitty`, assume **stale** unless **DECISIONS** says otherwise. Prefer editing the **canonical** file in the table above.

---

## Troubleshooting

macOS **`Icon\r`** metadata inside **`venv/`** can break imports (e.g. `jsonschema`). Remove with `find … -name 'Icon*' -delete` under the affected package, or reinstall in the venv.
