# Image Lab Architecture Harvest — Kitty vs InvokeAI & upstream ComfyUI

**Date:** 2026-07-20
**Status:** Research-only audit — no Kitty runtime modified
**Scope:** Kitty `Image Lab` (Draw Things + ComfyUI) vs. InvokeAI (read-only ref) and upstream ComfyUI (read-only ref, integration-correctness only)

---

## 0. Repository Identifiers

| Item | Value |
|---|---|
| **Kitty branch** | `feat/deeptutor-dth04-dth05` |
| **Kitty HEAD SHA** | `d7f7a8d306858258862a3d155fa41ae152d3a249` |
| **Kitty origin/main SHA** | `d7f7a8d306858258862a3d155fa41ae152d3a249` |
| **Kitty working tree** | unrelated in-progress DTH-04/DTH-05 changes (`.claude/HANDOFF.md`, `.claude/STATE.md`, `.gitignore`, `gateway/tutor.py`, `gateway/skill_import.py`) — **not part of this audit, left untouched** |
| **InvokeAI remote** | `https://github.com/invoke-ai/InvokeAI.git` |
| **InvokeAI inspected SHA** | `82e26811264701477683cfc937d05c6977c5ecda` |
| **InvokeAI license** | **Apache-2.0** (safe to study / reimplement; carry `NOTICE` attribution) |
| **ComfyUI remote** | `https://github.com/comfyanonymous/ComfyUI.git` |
| **ComfyUI inspected SHA** | `66655153499f89052aa72d5a869f556b25f0e9c6` |
| **ComfyUI license** | **GNU GPL-3.0** (copyleft — **API-only integration; never copy ComfyUI source into Kitty**) |

### Current Draw Things integration files (Kitty)
- `mcp/imagen/engines/adapters.py:37` — `DrawThingsHttpAdapter` (A1111 `/sdapi/v1/{txt2img,img2img}` over httpx)
- `mcp/imagen/engines/drawthings.py:22` — `DrawThingsEngine` (img2img via `init_image` + `denoising_strength`, `:77-102`)
- `mcp/imagen/engines/__init__.py:12` — registry entry `drawthings = _register(DrawThingsEngine())`
- `mcp/imagen/verify.py` + `mcp/imagen/tools/generate_until.py` — the **only** mounted surface that reaches the Draw Things engine
- `mcp/imagen/config.py` — `dt_url` setting
- `mcp/imagen/README.md` — documents the Draw Things engine

> The **legacy gateway Image Lab** (`gateway/image_gen.py`) does **not** integrate Draw Things at all — it is ComfyUI-only. Draw Things lives entirely inside `mcp/imagen/`.

### Current ComfyUI integration files (Kitty)
- `gateway/image_gen.py` — legacy ComfyUI-only client used by the chat UI Image Lab (`/image/status`, `/image/generate`, `/image/view`, `/image/history` in `gateway/routes/extended.py:260-306`)
- `mcp/imagen/engines/comfyui.py:163` — `ComfyuiEngine` (SD1.5/SDXL workflow builders, `_wf_sd15`/`_wf_sdxl`)
- `mcp/imagen/server.py:540` — `generate_image_comfy` (a **third** copy of the ComfyUI workflow builders)
- `notebooks/kitty_comfy_colab.ipynb` — Colab + cloudflared tunnel setup
- `.env.example:85-93` — `COMFY_URL` / `DT_URL`

---

## 1. Executive Verdict

**Kitty's Image Lab is real, working, and valuable — but it has drifted into three parallel implementations, leaks provider schema into product code, and lacks the durability/reproducibility basics that local creative work needs.**

The two backends the task assumes (Draw Things, ComfyUI) are both present and functional. Draw Things is reachable today only through the `generate_until` verified loop; the chat "Image Lab" UI talks to ComfyUI exclusively through a legacy gateway path. Neither path records provenance (seed/params), survives a restart, supports cancellation, or tracks image lineage. There is **no second gallery, queue, or artifact store to add** — Kitty already has `gateway/artifact_store.py`, `gateway/action_queue.py`, and `gateway/tasks.py` that the image paths simply do not use.

**Disposition summary:**
- **InvokeAI**: study-only. Its mechanisms (metadata+workflow persistence, lineage, queue/recovery, event contracts) are the right *shape* but are heavier than Kitty needs; Apache-2.0 means we may reimplement the ideas without copying.
- **ComfyUI**: integration-correctness reference only. Kitty's REST polling is fundamentally sound; the gaps are (a) no cancellation, (b) no error extraction from history `status_str`, (c) no durable copy of outputs, (d) hardcoded node schemas that will drift. ComfyUI is **GPL-3.0** — Kitty must remain a separate-process API client, never import or vendor its code.
- **Do NOT**: add InvokeAI as a dependency, replace the Image Lab, replace either backend, expose the ComfyUI node editor as Kitty's UI, or make ComfyUI's workflow schema Kitty's domain model.

**Bottom line:** adopt durability + provenance + cancellation onto the *existing* engine abstraction; converge the three implementations; keep both backends; stay API-only to ComfyUI.

---

## 2. Current-State Map (user action → persisted artifact)

### Path L — Chat "Image Lab" → ComfyUI (legacy gateway)
1. UI `gateway/kitty-chat/src/components/ImageGenPanel.tsx` posts to `/image/generate` (`gateway/kitty-chat/src/lib/gateway.ts:1082`).
2. `gateway/routes/extended.py:268` `image_generate` → `gateway/image_gen.generate(prompt)`.
3. `image_gen.py:137` builds a hardcoded ComfyUI workflow (`_wf_sd15` `:70` / `_wf_sdxl` `:97`), POSTs to `{COMFY_URL}/prompt` (`:148`), gets `prompt_id`.
4. `image_gen.py:113` `_poll` busy-waits `GET /history/{prompt_id}` every 4s up to 360s (blocking the HTTP handler).
5. On success, returns `{prompt_id, filename}`; an **in-memory** `_history` list (capped 20) records it (`image_gen.py:21,157-162`). **Seed is generated (`:66`) but never returned or stored.**
6. UI fetches the thumbnail via `/image/view/{filename}` → proxies `COMFY_URL/view` (`extended.py:283`). **The file lives in ComfyUI's output folder, not Kitty's store.**
7. Restart either process → `_history` and ComfyUI's in-memory history are both lost → gallery empty, `/image/view` 404s.

### Path M — MCP `imagen` server (Claude Code surface)
- `mcp/imagen/server.py` mounts monolithic inline tools (`generate_image`, `generate_image_comfy` `:540`, `edit_image` `:410`, `generate_until` `:824`, …).
- `server.py:857` imports **only** `generate_until` from the `tools/` refactor. The unified `generate`/`edit_image`/`batch_generate` tools and the `engines/` registry are **not mounted** (verified: no `import mcp.imagen.tools` / `import mcp.imagen.engines` outside `verify.py`).
- `generate_until` → `verify.py` → `engines.get(engine)` → `DrawThingsEngine` **or** `ComfyuiEngine`. **This is the only mounted path that can reach Draw Things.**
- Outputs go to `~/Pictures/kitty-gen` via `io.save_image` (`mcp/imagen/io.py:16`), which writes **non-atomically** (`path.write_bytes`, `:24`).
- No `artifact_store` / `action_queue` / `tasks` integration (grep `image` across those modules → zero hits).

**Neither path uses Kitty's durable infrastructure.** That is the central architectural fact.

---

## 3. Capability Matrix

Across the requested dimensions. **K** = Kitty, **DT** = Draw Things, **CU** = ComfyUI, **IA** = InvokeAI, **UC** = upstream ComfyUI.

| Dimension | Kitty + Draw Things | Kitty + ComfyUI | InvokeAI | upstream ComfyUI |
|---|---|---|---|---|
| Generation | txt2img + img2img (engine) | txt2img only (legacy + engine) | txt2img/img2img/SDXL/refine | arbitrary graph |
| Editing (inpaint/outpaint/upscale) | img2img only (unreachable as direct tool) | **none** (`comfyui.py:245` raises) | full canvas + mask | node-dependent |
| Queueing | none (M: batch semaphore) | none (busy-poll) | single-process session_queue | single daemon thread |
| Progress | none (M: verify scores) | none (4s poll, no events) | WS events (progress/complete/error) | WS + binary previews |
| Cancellation | none (no API) | **none** (CU has `/interrupt`) | cooperative `ThreadEvent` | `/interrupt` + job cancel |
| Recovery | none | none (orphan on GW restart) | startup reconciles `in_progress` | in-memory history lost on restart |
| Metadata | none stored | prompt_id+filename only | full workflow+seed+params per image | none returned to Kitty |
| Reproducibility | none | none (seed lost) | exact re-run via stored graph | seed-deterministic if resubmitted |
| Galleries | none (volatile list) | volatile `_history` | boards/projects/search | none |
| Lineage | none | none | weak (`init_image` in metadata) | none |
| Masking | none | none | first-class MASK images | node-dependent |
| Workflow reuse | none | hardcoded, duplicated ×3 | saved workflows | submit-API-format graph |
| Model mgmt | none (DT auto) | none (CU auto) | model_records + presets | `/models`, `/object_info` |
| Provider health | none | `is_available()` ComfyUI only | n/a (single backend) | `/system_stats` |
| Mobile UX | via chat UI | chat UI only | web PWA | web |
| Security | local-only, private rail | local-only | multi-user auth | **GPL-3.0 + custom-node RCE** |
| Tests | `test_drawthings_engine.py`, `test_imagegen_v2.py` | `ImageGenPanel.test.tsx` | extensive queue/image suite | n/a (external) |

**Reading:** Kitty is weakest exactly where local creative work hurts most — provenance, durability, cancellation, lineage. InvokeAI and ComfyUI are both stronger on those, but for reasons Kitty can borrow *conceptually* without adopting their weight.

---

## 4. Gap Register (verified gaps only)

| # | Gap | Evidence | Provider | Impact | Severity | Type | Best external ref | Worth it? |
|---|---|---|---|---|---|---|---|---|
| G1 | No durable provenance/metadata; seed lost; history in-memory | `image_gen.py:21,66,157-162`; `io.py` writes to `~/Pictures` not store | both | Can't re-run exactly; gallery empty after restart; no reproducibility | High | reliability+product | InvokeAI `image_records_sqlite.py`, `metadata.py:CoreMetadataInvocation` | **Yes** |
| G2 | No cancellation; blocking 6-min HTTP request; no job store | `image_gen.py:113-125` (busy-poll in handler); `extended.py:269` awaits | ComfyUI | User can't stop a runaway gen; GW worker blocked; orphan on crash | High | reliability+UX | ComfyUI `server.py:1150 /interrupt`; InvokeAI `cancel_event` | **Yes** |
| G3 | No image lineage (parent/child) anywhere | edits/variations are orphaned files; `comfyui.py:245` edit raises | both | "show everything derived from X" impossible; no settings reuse chain | Medium | product | InvokeAI `metadata.init_image` (weak) — Kitty should do better | Medium |
| G4 | Non-atomic persistence; outputs live outside Kitty store | `io.py:24` `write_bytes`; ComfyUI output folder not copied | both | torn file on crash; ComfyUI restart loses outputs → 404 | Medium | reliability | write-temp+rename; copy-on-success | **Yes** |
| G5 | Three parallel impls; ComfyUI workflow code ×3; Draw Things not first-class; UI contradiction | `image_gen.py:70-110`, `server.py:275-358`, `engines/comfyui.py:70-155`; `server.py:857` only mounts `generate_until`; `ProviderCenter.tsx:38-41` says ComfyUI "not wired" | both | maintenance drift; users get different behavior per surface; UI lies | High | architecture+trust | converge onto `engines/` abstraction | **Yes** |
| G6 | No per-engine health/capability for Draw Things; legacy only probes ComfyUI | `image_gen.py:128 is_available()` ComfyUI-only | Draw Things | DT outages silent; no honest status | Medium | reliability+UX | `is_available` per engine | **Yes** |
| G7 | No orphan reconciliation / crash recovery | in-memory history + ComfyUI in-memory history; no job DB | ComfyUI | GW dies mid-poll → lose `prompt_id` → orphaned CU job | Medium | reliability | InvokeAI `_set_in_progress_to_canceled` | Medium |
| G8 | ComfyUI history `status_str` not checked; errored job polled to timeout | `image_gen.py:119` only checks `prompt_id in hist`, not `status.status_str` | ComfyUI | misleading `TimeoutError` instead of real error; violates fail-loud | Medium | reliability+trust | read `status.status_str=="error"` + `execution_error` | **Yes** |
| G9 | Editing unsupported on the chat Image Lab path | `comfyui.py:245` NotImplementedError; DT img2img `:77` unreachable as direct tool | ComfyUI (chat) | "Image Lab" is txt2img-only; no img2img/variation in UI | Medium | product | route via engine abstraction | Medium |

---

## 5. Adopt / Adapt / Study / Reject / Already Covered

| Recommendation | Disposition | Exact code cited | Notes |
|---|---|---|---|
| Durable image-job + metadata store (seed/params/engine/output) | **Adopt** | InvokeAI `image_records_sqlite.py:151`, `metadata.py:188` → Kitty `gateway/artifact_store.py` | Reuse Kitty's SQLite; capture what InvokeAI captures |
| ComfyUI `/interrupt` + job record for cancellation/reconcile | **Adapt** | ComfyUI `server.py:1150`, `execution.py:1316`; InvokeAI `session_queue_sqlite.py:135` | Kitty adds a `prompt_id`→job row; cancel calls `/interrupt` |
| Atomic write (temp+rename) + copy output into Kitty store on success | **Adopt** | Kitty `io.py:24` (fix) | Trivial; survives ComfyUI restart |
| Read `status.status_str` / `execution_error` instead of polling-to-timeout | **Adapt** | ComfyUI `execution.py:1287`; Kitty `image_gen.py:119` | Honest failure (Constitution Art. I) |
| Provider-neutral lineage table (parent_id, kind) | **Adapt** | InvokeAI `metadata.py:228 init_image` (too weak) → Kitty new `image_lineage` table | Kitty should exceed InvokeAI's implicit model |
| Converge 3 impls onto `engines/` abstraction; retire legacy `image_gen.py` from UI path | **Adopt** | Kitty `engines/base.py`, `adapters.py:37`, `image_gen.py:70-110`, `server.py:275-358` | Single source of ComfyUI workflow builders |
| Make Draw Things + ComfyUI first-class in chat Image Lab via engine layer | **Adopt** | Kitty `extended.py:268`, `engines/__init__.py:12`, `ProviderCenter.tsx:38` | Fix contradiction; both backends in UI |
| Per-engine `is_available` for Draw Things + ComfyUI | **Adopt** | Kitty `image_gen.py:128`; `adapters.py` (add DT health) | Honest status |
| Pin ComfyUI commit + re-validate workflow via `/object_info` | **Adapt** | ComfyUI `server.py:790 /object_info`, `execution.py:1121 validate_prompt` | Defend against node-schema drift |
| WS progress streaming | **Study** | ComfyUI `server.py:269` WS, `execution.py:820 execution_success`; Kitty polls `:116` | Polling already correct; WS is lossy (§9) — nice-to-have only |
| InvokeAI gallery/boards/projects/search UI | **Study** | InvokeAI `boards_default.py`, `image_records_sqlite.py:227` `LIKE` search | Kitty's gallery is a volatile list; borrow the *concept*, not the tables |
| InvokeAI Socket.IO event contract | **Study** | InvokeAI `events_common.py`, `sockets.py` | Template only if Kitty adopts WS |
| InvokeAI model/preset manager | **Reject** | InvokeAI `model_records_sql.py:296` | Kitty backends auto-discover models; overkill |
| Adopt InvokeAI as a runtime dependency | **Reject** | (license Apache-2.0 but unnecessary) | Violates "minimal dependencies" + leverage-before-reinvention |
| Copy any ComfyUI source | **Reject** | ComfyUI `LICENSE` GPL-3.0 | API-only integration mandated |
| Expose ComfyUI node editor as Kitty's UI | **Reject** | ComfyUI `nodes.py` | Graph is execution repr, not Kitty UX |
| Second gallery/queue/artifact store | **Reject** | Kitty already has `artifact_store`/`action_queue` | Would duplicate existing systems |

---

## 6. Do-Not-Reinvent List

Mechanisms already solved well upstream that Kitty should reuse **conceptually** (reimplement, don't copy — especially ComfyUI, which is GPL):

1. **Prompt→image correlation key = `prompt_id`** (ComfyUI `server.py:1083`). Kitty already grabs it (`image_gen.py:151`); keep it as the job PK.
2. **Output discovery via `/history/{prompt_id}` → `outputs[<node>].images[]` → `/view`** (ComfyUI `server.py:1035,517`). Kitty's poll loop already does this shape; just add error extraction.
3. **Cancellation = `/interrupt` with optional `prompt_id`** (ComfyUI `server.py:1150`). Targeted + global; Kitty adds nothing new, just calls it.
4. **Reproducibility = persist the full request (prompt/seed/params/workflow)** (InvokeAI `metadata.py:188`, `images_default.py:171 get_workflow`). Kitty's `artifact_store` can hold this.
5. **Crash recovery = reconcile `in_progress` rows on startup** (InvokeAI `session_queue_sqlite.py:135`). Kitty's job row gets a `status` column; on GW start, flip stuck rows.
6. **Atomic file write = temp file + `os.replace`** (universal). Fix `io.py:24`.
7. **Capability negotiation = `/system_stats` + `/object_info`** (ComfyUI `server.py:709,790`). Kitty should re-validate its hardcoded workflow against `/object_info` after a ComfyUI version bump.

---

## 7. Do-Not-Import List

Architecture/features that conflict with Kitty, duplicate existing systems, or add unnecessary complexity:

1. **InvokeAI as a dependency** — violates minimal-deps + leverage-before-reinvention; Kitty's needs are a strict subset.
2. **ComfyUI source / custom nodes** — GPL-3.0 copyleft; arbitrary-code-execution surface. Keep ComfyUI a separate, low-privilege, network-egress-firewalled process.
3. **InvokeAI multi-user auth / boards / projects** — Kitty is single-user local-first; these are SaaS scaffolding.
4. **InvokeAI Socket.IO + `Invoker` DI container** — heavy; Kitty's FastAPI + `artifact_store` already cover the need at smaller cost.
5. **ComfyUI node-editor UX** — graph is an execution representation, not Kitty's conversational product surface.
6. **A second gallery/queue/artifact model** — Kitty already has `artifact_store`, `action_queue`, `tasks`. Point images at those.
7. **ComfyUI `/internal/*` endpoints** — explicitly unstable/frontend-only (`api_server/routes/internal/internal_routes.py`); do not depend on them.
8. **Making ComfyUI's workflow JSON Kitty's canonical domain model** — keep a provider-neutral `ImageJob` record; store provider-specific params as JSON, don't promote node schemas into product types.

---

## 8. Provider Abstraction Review

**Current state:** Kitty has a *good* abstraction in `mcp/imagen/engines/base.py` (`Engine` ABC) + `adapters.py` (`ImagegenAdapter` isolates Draw Things/A1111 transport). But the **legacy chat Image Lab bypasses it entirely** — `gateway/image_gen.py` hardcodes ComfyUI node `class_type` strings and `inputs` wiring directly in product code (`image_gen.py:70-110`). That is schema leakage: the product layer knows ComfyUI's `CheckpointLoaderSimple`/`LoraLoader`/`KSampler` internals.

**Verdict:** the domain model is *mostly* clean (prompt + engine + params), but two real leaks exist:
- **Leak 1 (generation request):** legacy path constructs a ComfyUI-specific graph; the engine layer constructs its own. Two graph builders for the same backend. → collapse to one (in `engines/comfyui.py`), used by both surfaces.
- **Leak 2 (editing):** `ComfyuiEngine.edit` raises `NotImplementedError` (`comfyui.py:245`); `DrawThingsEngine` supports img2img but is unreachable as a direct tool. The product can't express "img2img" uniformly. → add `init_image`/`denoising_strength` to the `Engine` interface; both backends implement or explicitly decline.

**Recommendation (only where leakage causes a real problem):**
- Route the chat Image Lab UI through the `engines/` abstraction (a thin router replacing `image_gen.py`'s direct ComfyUI calls), so Draw Things and ComfyUI are both first-class and the product layer stops naming ComfyUI nodes.
- Keep provider-specific extensions (LoRAs, NSFW, workflow templates) as **engine-scoped params**, never product types.
- Add a provider-neutral `ImageJob` record (engine, kind, seed, params_json, output_path, parent_id) as the single source of truth; both engines write it.

This is the architectural linchpin: it removes leak #1/#2 and unblocks G1/G3/G5/G9 simultaneously.

---

## 9. ComfyUI Integration Hardening Review

Kitty's REST polling is fundamentally sound. Verdict per required item (ComfyUI SHA `66655153499f89052aa72d5a869f556b25f0e9c6`):

| Item | Verdict | Evidence |
|---|---|---|
| Queue identifiers | **OK** (track `prompt_id`) | `image_gen.py:151`; ComfyUI `server.py:1083` |
| WebSocket reconnects | **N/A today** — Kitty polls, avoiding WS lossiness. If WS adopted later, must reconcile via `/history` (ComfyUI `server.py:287` replays only `executing`; `execution_success` is per-`client_id` and lost on sid change) | ComfyUI `server.py:269,287` |
| History lookup | **OK** | `image_gen.py:117` `GET /history/{prompt_id}` |
| Cancellation | **GAP** — Kitty has none; CU supports `/interrupt` | ComfyUI `server.py:1150`; Kitty `image_gen.py` (no call) |
| Workflow drift | **RISK** — Kitty hardcodes node `class_type` + `INPUT_TYPES` assumptions; CU schemas drift per version; no `/object_info` re-validation | `image_gen.py:70-110`; ComfyUI `server.py:790`, `execution.py:1121` |
| Custom-node failures | **Low risk today** (Kitty submits only built-in nodes) — **high risk if user workflows accepted** (RCE via `nodes.load_custom_node`, `nodes.py:2227`) | ComfyUI `nodes.py:2227` |
| Missing outputs | **GAP** — Kitty doesn't read `status.status_str`; errored job polled to 360s then `TimeoutError` | `image_gen.py:119`; ComfyUI `execution.py:1287` |
| Malformed graphs | **OK** — CU returns 400 + `node_errors`; Kitty raises `RuntimeError(r.text)` | `image_gen.py:150`; ComfyUI `server.py:1126` |
| Arbitrary path input | **Low risk** — Kitty sends only prompts, no user workflows/paths; CU guards `/view` (`server.py:539`) but node-internal file access is unguarded | ComfyUI `server.py:539,414` |
| Orphaned jobs | **GAP** — GW death loses `prompt_id` (volatile `_history`); CU job may keep running | Kitty `image_gen.py:21` |
| Server restart | **GAP** — CU history is in-memory (`MAXIMUM_HISTORY_SIZE`); restart → `/history` 404 → `/image/view` 404 | ComfyUI `execution.py:1242`; Kitty `extended.py:295` |
| Version compatibility | **RISK** — Kitty pins no CU commit; node interfaces not guaranteed stable | ComfyUI `server.py:790`; `comfy_api/feature_flags.py` |

**Hardening actions (all Adapt, no ComfyUI code copied):** wire `/interrupt`; read `status.status_str`; copy output into Kitty store on success; pin CU commit + re-validate via `/object_info`; never accept user-supplied workflows (RCE surface).

---

## 10. Image Lineage Proposal (not implemented)

A **small, provider-neutral** model — no graph, no InvokeAI weight:

```sql
-- lives in Kitty's existing SQLite (reuse artifact_store DB)
CREATE TABLE image_jobs (
  id          INTEGER PRIMARY KEY AUTOINCREMENT,
  prompt_id   TEXT,                       -- ComfyUI prompt_id or DT job id
  engine      TEXT NOT NULL,              -- 'drawthings' | 'comfyui'
  kind        TEXT NOT NULL,              -- 'txt2img'|'img2img'|'variation'|'upscale'|'inpaint'
  parent_id   INTEGER REFERENCES image_jobs(id),  -- NULL = generated from prompt
  seed        INTEGER,
  params_json TEXT,                       -- provider-specific (LoRA/strength/size) as JSON
  output_path TEXT NOT NULL,              -- path inside Kitty's store (not CU output folder)
  created_at  TEXT NOT NULL
);
```

This captures every relationship the task lists: *generated from prompt* (parent_id NULL), *variation of / edited from / inpainted from / upscaled from* (parent_id + kind), *workflow reused from generation* and *settings reused from generation* (params_json copied to a new row with a new prompt_id). Provider-neutral: Draw Things and ComfyUI both write the same columns; CU/IA-specific knobs live in `params_json`. Index `parent_id` for "show everything derived from X". **No new dependency, no schema promotion of provider types.**

---

## 11. Ranked Top Ten Findings

Ranked by user value + reliability gain + architectural leverage − implementation cost − risk.

1. **Converge the three image implementations onto `engines/`; make Draw Things + ComfyUI first-class in the chat Image Lab; fix `ProviderCenter.tsx` contradiction.** (architecture/trust; high value; medium cost; unblocks G5/G9)
2. **Durable image-job + metadata store (seed/params/engine/output) persisted to Kitty's SQLite.** (reliability/product; high value; low cost; G1)
3. **Wire ComfyUI `/interrupt` + job record so in-flight jobs cancel and survive gateway restart.** (reliability; high value; medium cost; G2/G7)
4. **Atomic persistence (temp+rename) + copy ComfyUI output into Kitty store on success.** (reliability; medium value; low cost; G4/server-restart)
5. **Extract real errors from ComfyUI `status.status_str` / `execution_error` instead of polling-to-timeout.** (honest-status; medium value; low cost; G8 — Constitution Art. I)
6. **Provider-neutral image lineage table (parent/child).** (product; medium value; low cost; G3)
7. **Per-engine `is_available` for Draw Things + ComfyUI; honest UI states.** (UX/reliability; medium value; low cost; G6)
8. **Pin ComfyUI commit + re-validate hardcoded workflow via `/object_info` after bumps.** (reliability; medium value; low cost; workflow-drift risk)
9. **Collapse triple-duplicated ComfyUI workflow builders into `engines/comfyui.py`.** (maintenance; medium value; low cost; G5)
10. **(Optional, low priority) WS progress streaming** reconciled via `/history` — only if UX demands it; polling is already correct. (UX; low value; high cost)

---

## 12. Small Implementation Packets

### Packet IMG-01 — Durable image-job + metadata store
- **Problem:** no provenance; seed/params lost; history volatile (G1).
- **User value:** exact re-runs; gallery survives restart; reproducibility.
- **Kitty files:** `gateway/artifact_store.py` (new table) or new `gateway/image_jobs.py`; `gateway/image_gen.py` (write row); `mcp/imagen/io.py` (write row).
- **Refs:** InvokeAI `image_records_sqlite.py:151`, `metadata.py:188`.
- **Scope:** SQLite `image_jobs` table (§10); record on every generation.
- **Non-goals:** UI, lineage graph, WS.
- **Acceptance:** store→retrieve round-trip; row survives process restart; seed persisted.
- **Tests:** `tests/test_image_jobs.py` (round-trip + restart).
- **Provider cases:** both Draw Things + ComfyUI write the row.
- **Deps:** none. **Migration:** new table, forward-only. **Risk:** Low. **Tier:** T0. **Free worker:** Yes. **ADR:** No (extends artifact_store).

### Packet IMG-02 — ComfyUI cancellation + job reconciliation
- **Problem:** no cancel; orphaned jobs on GW restart (G2/G7).
- **User value:** stop runaway gens; no silent orphans.
- **Kitty files:** `gateway/image_gen.py` (call `/interrupt`), `gateway/routes/extended.py` (cancel route), `gateway/image_jobs.py` (status column + startup reconcile).
- **Refs:** ComfyUI `server.py:1150 /interrupt`, `execution.py:1316`; InvokeAI `session_queue_sqlite.py:135`.
- **Scope:** add cancel endpoint; flip stuck `in_progress` rows to `canceled` on GW start.
- **Non-goals:** Draw Things cancel (no API); WS.
- **Acceptance:** mid-gen cancel stops CU; GW restart reconciles stuck row.
- **Tests:** `tests/test_image_cancel.py` (mock CU `/interrupt`).
- **Provider cases:** ComfyUI only (Draw Things: document "no cancel API").
- **Deps:** none. **Risk:** Medium. **Tier:** T1. **Free worker:** partial. **ADR:** No.

### Packet IMG-03 — Atomic persistence + copy output into Kitty store
- **Problem:** torn files; ComfyUI restart loses outputs (G4).
- **User value:** no corrupted images; outputs survive CU restart.
- **Kitty files:** `mcp/imagen/io.py:24` (temp+rename); `gateway/image_gen.py` (copy `/view` bytes into store on success).
- **Scope:** write-temp-rename; on success, fetch CU output and store locally.
- **Non-goals:** CU restart handling beyond copy.
- **Acceptance:** crash mid-write leaves no torn file; output present after simulated CU restart.
- **Tests:** `tests/test_image_persist.py`.
- **Provider cases:** both.
- **Deps:** none. **Risk:** Low. **Tier:** T0. **Free worker:** Yes. **ADR:** No.

### Packet IMG-04 — Provider-neutral image lineage
- **Problem:** no parent/child tracking (G3).
- **User value:** "derived from X"; settings reuse chain.
- **Kitty files:** `gateway/image_jobs.py` (`parent_id` column per §10); call sites set parent.
- **Scope:** `parent_id` + `kind` on every gen/edit/variation.
- **Non-goals:** UI/graph.
- **Acceptance:** variation row links to source; query by parent.
- **Tests:** `tests/test_image_lineage.py`.
- **Provider cases:** both.
- **Deps:** none. **Risk:** Low. **Tier:** T0. **Free worker:** Yes. **ADR:** No.

### Packet IMG-05 — Unify chat Image Lab onto engine abstraction
- **Problem:** legacy path leaks ComfyUI schema; Draw Things not in UI; ProviderCenter contradiction (G5/G9).
- **User value:** both backends first-class; honest UI; one workflow builder.
- **Kitty files:** `gateway/routes/extended.py` (route via `engines/`), `gateway/kitty-chat/src/components/ImageGenPanel.tsx` (engine select), `ProviderCenter.tsx:38` (fix note), retire `image_gen.py` from UI path (keep engines/comfyui.py).
- **Refs:** `engines/base.py`, `adapters.py:37`, `engines/__init__.py:12`.
- **Scope:** thin router; collapse 3 workflow builders → 1 in `engines/comfyui.py`.
- **Non-goals:** new providers; node editor.
- **Acceptance:** UI can pick Draw Things or ComfyUI; single ComfyUI builder; ProviderCenter truthful.
- **Tests:** `ImageGenPanel.test.tsx` (both backends), `tests/test_image_router.py`.
- **Provider cases:** Draw Things + ComfyUI.
- **Deps:** none. **Risk:** Medium. **Tier:** T1. **Free worker:** No (UI + divergence). **ADR:** Recommend ADR note (provider abstraction) — Jacob decides.

### Packet IMG-06 — Per-engine health + ComfyUI version pin
- **Problem:** DT outages silent; workflow drift (G6, §9 drift).
- **User value:** honest status; no silent break on CU upgrade.
- **Kitty files:** `mcp/imagen/engines/adapters.py` (DT `is_available`), `gateway/image_gen.py` (CU `is_available` already), config pin (`COMFY_COMMIT`), `/object_info` re-validation.
- **Scope:** health per engine; pin + validate.
- **Acceptance:** DT down → honest status; CU upgrade flagged if workflow invalid.
- **Tests:** `tests/test_image_health.py`.
- **Provider cases:** both.
- **Deps:** none. **Risk:** Low/Medium. **Tier:** T0/T1. **Free worker:** Yes. **ADR:** No.

---

## 13. First-Packet Recommendation

**IMG-01 — Durable image-job + metadata store.**

It maximizes reliability + user value (reproducibility, restart-surviving gallery, exact re-runs) with **minimal architectural disruption**: it adds one SQLite table to Kitty's existing store, writes a row on every generation, and touches no provider schema. Low risk, no new dependencies, free-worker capable, no ADR required. It is also the **prerequisite** for IMG-02 (job record), IMG-03 (output_path), IMG-04 (lineage), and IMG-05 (engine-neutral record) — so it unlocks the rest in order.

---

## 14. Documentation Updates

- **This file** is the audit deliverable, recorded in Kitty's canonical audit location `docs/` (alongside `AUDIT_DEEPTUTOR_ARCHITECTURE_HARVEST_2026-07-20.md`). No new documentation hierarchy invented.
- **No index/roadmap edit justified** — Kitty has no audit index file; adding one would invent hierarchy. The DeepTutor audit set the same precedent (doc-in-`docs/` only).
- Recommended follow-ups (when IMG-01 lands): update `docs/tutor-design.md`-style note? No — image docs are `mcp/imagen/README.md` and `.agents/skills/image-gen/SKILL.md`; those should be reconciled in IMG-05, not here.

---

## 15. Final Report

- **Kitty branch:** `feat/deeptutor-dth04-dth05`
- **Kitty HEAD / origin/main:** `d7f7a8d306858258862a3d155fa41ae152d3a249`
- **Kitty working tree:** unrelated DTH-04/DTH-05 in-progress (untouched by this audit)
- **InvokeAI remote / SHA:** `invoke-ai/InvokeAI` @ `82e26811264701477683cfc937d05c6977c5ecda` (Apache-2.0)
- **ComfyUI remote / SHA:** `comfyanonymous/ComfyUI` @ `66655153499f89052aa72d5a869f556b25f0e9c6` (GPL-3.0)
- **Current Draw Things files:** `mcp/imagen/engines/{adapters.py,drawthings.py,__init__.py}`, `verify.py`, `tools/generate_until.py`, `config.py`
- **Current ComfyUI files:** `gateway/image_gen.py`, `mcp/imagen/engines/comfyui.py`, `mcp/imagen/server.py:540`, `notebooks/kitty_comfy_colab.ipynb`, `.env.example`
- **Files changed (this audit):** `docs/AUDIT_IMAGELAB_ARCHITECTURE_HARVEST_2026-07-20.md` (new, only)
- **Commit SHA:** _(see commit below)_
- **Validation:** `git diff --check` clean; link check noted below
- **Executive verdict:** Keep both backends; stay API-only to ComfyUI (GPL); converge three implementations onto the existing `engines/` abstraction; add durability/provenance/cancellation/lineage onto Kitty's own store. Study InvokeAI's *shape*, adopt none of its weight.
- **Verified Kitty gaps:** G1–G9 (§4).
- **Top ten:** §11.
- **Recommended first packet:** IMG-01 (§13).
- **Decisions requiring Jacob's judgment:**
  1. **Approve IMG-05's engine abstraction convergence** (retire legacy `image_gen.py` from the UI path, make Draw Things first-class)? It is the highest-leverage change but touches the chat UI + `ProviderCenter.tsx` and is T1.
  2. **Should Kitty ever accept user-supplied ComfyUI workflows?** Current harvest says **no** — it is an RCE + path-traversal surface (ComfyUI `nodes.py:2227`, `server.py:414`). Keep Kitty submitting only its own hardcoded/built-in-node workflows.
  3. **ComfyUI runs as what privilege?** Recommended: low-privilege user, chrooted/jailed filesystem, egress firewall (given `comfy_api_nodes` outbound calls). This is an ops decision, not code.
  4. **WS progress streaming (finding #10)** — adopt now or defer? Polling is correct; WS adds complexity for marginal UX gain.
