# Packet 025 — Imagegen pipeline v2: local-first, criteria-verified loop

- **Status:** 📋 spec authored 2026-07-05 (Jacob's explicit request, verbatim
  intent below), executor-ready. Side track: parallel to any wave, does not
  gate move-in.
- **Best executor:** Claude Code for the build; Jacob for installs, model
  downloads, and taste calls. First verified-loop rubric reviewed together.
- **Jacob's intent (2026-07-05):** *"set me up for success by having the
  proper tools, downloads, files, workflows, and processes in place to allow
  me to generate images I want. Should be able to set a loop and AI works at
  it until the output is verified against a set of criteria. I will not be
  using fal anymore, too expensive. Pre-setup strategies and workplaces
  where we can do it cheaply/free, then the tools to step it up. In addition
  to ComfyUI I have Draw Things. Models and LoRAs picked should help me lock
  a face, and proper male anatomy."*

## What already exists (verified against the code 2026-07-05, do not rebuild)

**⚠️ Location preflight (Jacob, 2026-07-05: "it's in Projects, not kitty"):**
the live imagen server is likely its own checkout under `~/Projects/`, not
this repo's `mcp/imagen/` copy. Step 0 of the build: find which path the
MCP client config actually points at (`~/Library/Application
Support/Claude/claude_desktop_config.json` and/or `.claude` settings), diff
it against this repo's copy, and build in the live one. If the two have
drifted, reconcile FIRST and decide the single source of truth (record it
in `docs/DECISIONS.md`) — do not ship features into a dead copy. Everything
below describes the code as it exists in this repo's `mcp/imagen/`; adjust
paths to the live checkout as needed.

`mcp/imagen/` (this repo's copy) is a real, tested MCP server (38+ tests): engine registry
(`engines/__init__.py` — comfyui, dalle, imagen4, nano_banana/Gemini),
ComfyUI workflow builders with LoRA loader nodes (`_wf_sd15`, `_wf_sdxl`,
`COMFY_URL` default `http://127.0.0.1:8188`), character/avatar system
(`save_character`, `set_avatar`, `generate_with_avatar`), batch + cache +
retry (`cache.py`, `retry.py`), env-overridable model names (`config.py`),
output to `~/Pictures/kitty-gen`. Plus fal.ai FLUX/PuLID tools — **being
retired by this packet.**

**Verified externally:** Draw Things exposes an A1111-compatible HTTP API
when its API Server is enabled — `GET http://localhost:7860/` returns
current setup; `POST /sdapi/v1/txt2img` takes the standard A1111 payload
(prompt, negative_prompt, width, height, seed, steps, cfg_scale) and
returns base64 images.
Draw Things official project: https://github.com/drawthingsai/draw-things-community

That compatibility is the architectural centre of this packet: **one new
engine speaks to Draw Things locally AND to any A1111/Forge server on a
rented GPU later.** The step-up path from free to paid is a URL change.

## Exact scope

1. **`mcp/imagen/engines/drawthings.py`** — A1111-protocol engine.
   `DT_URL` env (default `http://127.0.0.1:7860`), standard payload, base64
   decode, same `Engine` protocol as `comfyui.py`. Errors distinguish "Draw
   Things not running / API server not enabled" (actionable message naming
   the settings toggle) from generation failure. Because it's plain A1111
   protocol, `DT_URL` pointed at a RunPod/Vast box is the paid tier — no new
   code.

2. **Retire fal.** Remove the fal tools from `server.py` (git keeps the
   history), drop `FAL_KEY` from `.env.example`, and update
   `.claude/rules/initiative.md` — it still tells every session to offer
   `enhance_realism_fal` after generations. Replace with the local pipeline
   equivalents (upscale + face-restore via ComfyUI/Draw Things img2img).

3. **The verified loop — `mcp/imagen/verify.py` + a `generate_until` tool.**
   `generate_until(prompt, criteria_name, engine, max_attempts=8,
   keep=3)`: generate → score → keep best-N → stop early when a candidate
   passes all hard criteria, else iterate (reseed; optionally let a local
   LLM adjust the prompt between attempts, off by default). Every attempt
   logged to `~/Pictures/kitty-gen/runs/<run-id>/attempts.jsonl` with
   scores, seed, and payload so a good result is always reproducible.
   Scorers, each independent and optional per criteria file:
   - **`face_match`** — InsightFace embedding cosine distance against a
     reference set (`config/imagen/faces/<character>/*.png`). Free, local,
     fast, and the only scorer trusted as a *hard* gate. This is the
     face-lock: characters stop drifting because a number says so, not
     because the prompt begged.
   - **`vision_rubric`** — a local VLM via Ollama (e.g. `qwen2.5-vl:7b`)
     answers yes/no per rubric line (anatomy correct, right number of
     hands, composition matches brief, no artifacts). Soft gate by default:
     VLMs are fallible judges, so rubric failures rank candidates rather
     than discard them, unless a line is marked `hard:`.
   - **`mechanical`** — resolution floor, file-size sanity, black/blank
     detection. Always on.
   Criteria live in `config/imagen/criteria/<name>.yaml` — human-editable,
   one file per recurring goal (e.g. `character-jace.yaml`,
   `photoreal-portrait.yaml`).

4. **Face-lock workflow (docs + one tool, no training code in v1):**
   - Stage 1, today: reference-based lock — 8–12 approved images of the
     character into `config/imagen/faces/<name>/`, `face_match` gates
     every future generation against them. Works with any engine.
   - Stage 2, when Stage 1 plateaus: train a character LoRA from the
     approved set — Civitai's on-site trainer (cheap, runs on their GPUs)
     or Draw Things' on-device LoRA training on Apple Silicon (free,
     overnight). The packet documents both runbooks; v1 ships no training
     code. Trained LoRA loads in both ComfyUI (loader nodes already built)
     and Draw Things (LoRA import).

5. **Model strategy (the downloads, so the tools have something to run).**
   Documented in `mcp/imagen/README.md` as the setup runbook:
   - **Base checkpoints (SDXL-class, Civitai):** a Pony Diffusion V6 XL or
     Illustrious-XL derivative as the anatomy-competent base — these model
     families are trained on far broader anatomy than base SDXL and are the
     established answer for correct male anatomy; plus one photoreal merge
     of the same family for realism work. ~6.5 GB each — start downloads
     before a session.
   - **LoRAs (Civitai, filter by the chosen base family):** male-anatomy
     detail LoRAs for the base, plus the Stage-2 character LoRA when
     trained. Registry of picks (name, version, hash, trigger words) in
     `config/imagen/models.yaml` so sessions stop re-deriving them.
   - **Face stack for ComfyUI (optional, Stage 1.5):** IPAdapter
     FaceID/InstantID nodes for reference-guided identity when pure
     prompting isn't enough. Documented, not blocking.
   - **Verifier model:** one local VLM via Ollama for `vision_rubric`.

6. **Cost tiers (the "workplaces"), documented in the same runbook:**
   - **Tier 0 — free, local, private:** Draw Things on the Air (own the
     queue overnight; quantized SDXL runs on Apple Silicon), ComfyUI local
     for scriptable workflows. All personal content stays on-machine.
   - **Tier 1 — free, cloud, limited:** Civitai on-site generation (daily
     free Buzz) for trying checkpoints/LoRAs *before* downloading 6 GB.
     Honest note: Colab/Kaggle free GPUs prohibit adult content — they are
     not a workplace for this pipeline, and pretending otherwise risks the
     account.
   - **Tier 2 — cheap, metered:** RunPod/Vast.ai spot GPU (a 3090/4090 at
     roughly $0.20–0.40/hr in recent pricing — verify at rental time)
     running A1111/Forge or ComfyUI. The drawthings engine (A1111
     protocol) and comfyui engine both work unchanged — set `DT_URL` /
     `COMFY_URL` to the pod. Pay only during sessions; this replaces fal
     at a fraction of per-image cost.

7. **Privacy rail (D10's spirit, new content class):** personal creative
   prompts and reference images are `personal_creative` — local engines
   only. The `generate_until` tool refuses to send a criteria run tagged
   `private: true` to dalle/imagen4/nano_banana (cloud), the same
   fail-toward-privacy default as `health_admin`. Cloud engines remain
   available for SFW/shareable work by explicit choice.

## Jacob's half (the setup runbook, ~30 min + downloads)

1. Draw Things (App Store, free) → Settings → **enable API Server**
   (127.0.0.1:7860, HTTP).
2. Pick the base checkpoint on Civitai (test-drive via free on-site
   generation first), download it + one photoreal merge + 2–3 anatomy
   LoRAs for that base. Import into Draw Things; same files symlinked into
   ComfyUI's `models/` if using Comfy.
3. `ollama pull qwen2.5-vl:7b` (or the VLM the build settles on).
4. Drop 8–12 approved reference images of the character into
   `config/imagen/faces/<name>/`.
5. First verified run together: write `config/imagen/criteria/<name>.yaml`,
   run `generate_until`, judge the survivors, tighten the rubric.

## Files likely touched

- `mcp/imagen/engines/drawthings.py` (new), `engines/__init__.py`
- `mcp/imagen/verify.py` (already on `main` — criteria loop; this slice
  builds the mockable adapter on top), `server.py` (`generate_until` tool;
  fal tools removed), `config.py` (DT_URL, verifier settings)
- `config/imagen/criteria/` + `config/imagen/models.yaml` (new)
- `mcp/imagen/README.md` (runbook), `.claude/rules/initiative.md` (de-fal),
  `.env.example`
- `tests/test_mcp_imagen.py` + new `tests/test_imagen/test_verify.py`,
  `test_drawthings_engine.py` (HTTP stubbed, same pattern as existing
  engine tests)

## Files NOT to touch

- `gateway/` — this pipeline is the MCP server's job; the gateway is not an
  image proxy in v1.
- Existing comfyui/dalle/imagen4/nano_banana engines beyond registry edits.

## Acceptance criteria (commands, not vibes)

- [ ] `./venv/bin/python -m pytest tests/test_mcp_imagen.py tests/test_imagen/ -q`
  green: drawthings engine happy/error paths (stubbed HTTP), verify loop
  (stubbed scorers) stops early on pass / exhausts attempts / keeps best-N /
  writes attempts.jsonl, `private: true` + cloud engine raises.
- [ ] `ruff check` / `mypy` clean on new files.
- [ ] Manual against a real Draw Things or A1111 endpoint (Jacob's Air, or
  any A1111 server for the executor): one `generate_until` run completes,
  attempts.jsonl shows real scores, best image lands in the run folder.
- [ ] `grep -rn "fal" .claude/rules/ mcp/imagen/server.py` returns nothing
  live (history is git's job).
- [ ] `mcp/imagen/README.md` runbook is complete enough that Jacob does his
  half without asking a single "where does this file go" question.

## Jacob reviews

- The first verified run's survivors vs. rejects — is the rubric judging
  what he actually cares about?
- Face-lock threshold: too strict throws away good variety, too loose
  drifts. One number in the criteria file.

## Too broad if

- v1 grows LoRA *training* code (runbooks only), a web UI, a queue service,
  or gateway routes.
- The verify loop starts editing images (upscale/inpaint are existing
  tools chained manually or in a later packet).
- Any scorer other than `face_match` becomes a hard gate by default.
