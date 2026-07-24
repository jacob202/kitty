# image studio and character system redesign: 2026-07-24

> **position in the kit**: concrete implementation plan for the image subsystem. takes input from `architecture-honesty.md` (what exists: comfyui wrapper, v1 character store, image job queue, page.tsx monolith), `repo-landscape.md` (no direct image-gen competitors found — kitty's companion+image integration is novel), and `kitty-vision-gap-analysis.md` (character consistency is a p2 gap, creative modalities are p3).

redesign proposal based on code analysis of image_gen.py, image_runner.py, image_characters.py, image_jobs.py, ImageStudio.tsx, ImageGenPanel.tsx, and the image-related sections of page.tsx. cross-referenced with memory system patterns where relevant (privacy gate in memory_policy.py, confidence decay in memory_weave.py).

---

## current state — what exists

### image_gen.py
- comfyui api wrapper. `load_workflow_template()` loads any workflow without type checking.
- four workflow types referenced (text2img, img2img, inpainting, upscale) but all loaded through the same generic loader — no per-type schema validation.
- progress polling via comfyui `/history/` endpoint.
- output to fixed `output_dir`. not configurable per request.

### image_characters.py
- v1 sqlite store: name, prompt, lora, negative_prompt, created_at, updated_at.
- crud api exists. honestly named "v1" in code.
- **no reference images** — character consistency relies entirely on prompt engineering and lora selection. no face embeddings, no pose references, no versioning, no gallery.

### image_jobs.py
- job lifecycle: pending → running → done (or failed).
- sqlite-backed queue. results stored as file paths.
- **no retry**, no timeout tracking, no priority, no scheduling.

### image_runner.py
- background thread (not asyncio) polling comfyui.
- reads from image_jobs queue.

### frontend — ImageStudio, ImageGenPanel, page.tsx
- ImageStudio: generation state, character selection, workflow selection.
- ImageGenPanel: prompt, negative prompt, lora selection, batch count.
- page.tsx: websocket for job updates, status polling, result display.
- **tightly coupled** — ImageStudio and ImageGenPanel are rendered inside the 1060-line page.tsx monolith. no independent route, no deep-linkable state, no image gallery, no browsing past generations.

---

## problems

### correctness and reliability
1. **single backend (comfyui only).** if comfyui is down, image generation is entirely unavailable.
2. **workflow templates are unvalidated.** mismatched templates produce opaque comfyui errors. no per-type schema.
3. **job queue has no retry.** transient failures (comfyui restart, oom) are permanent failures.
4. **job queue has no priority.** interactive generation and background batch share the same queue.

### feature gaps
5. **character store has no image references.** character consistency depends on prompt+lora alone. no face embeddings, no reference images, no versioning of character definitions.
6. **no output management.** generated images go to a fixed directory. no gallery, no browse by character/date/workflow, no parameter-preserving regeneration.
7. **no cross-modal integration.** image characters are unrelated to companion personality. no shared identity between what kitty generates visually and how kitty behaves in conversation.

### architecture
8. **frontend coupled to monolith.** ImageStudio and ImageGenPanel are deeply embedded in page.tsx. adding features to image generation means editing the monolith.
9. **image runner is thread-based, not asyncio.** can't compose with async operations like builder sub-tasks or memory consolidation. blocks.

---

## redesign

### phase 0 — frontend decoupling (DO FIRST)

**before building any new features, extract image components from the monolith.** this is the blocker for all subsequent work. adding features to the 1060-line page.tsx guarantees a larger refactor later.

**actions**:
- create independent `/images` route using next.js app router
- `ImageStudio` and `ImageGenPanel` become self-contained page components with their own layout
- url-encode character, workflow, and prompt parameters for deep linking
- image gallery view at `/images/gallery` — filter by character, workflow, date
- image detail view at `/images/[id]` — shows generation parameters, allows regeneration
- remove image-related state and websocket handling from page.tsx

**deliverable**: image studio works at `/images` with gallery, detail, and generation views. page.tsx no longer contains image code.

### phase 1 — character store v2

build on the honest v1 schema with image-backed character consistency.

**1a. reference images + face embeddings**

add to character store schema:

```sql
ALTER TABLE characters ADD COLUMN reference_images TEXT;  -- json array of file paths
ALTER TABLE characters ADD COLUMN face_embedding BLOB;     -- serialized numpy array, nullable
```

dependency evaluation for face embeddings:
- **insightface**: best accuracy but heavy dependency (onnxruntime, model download). requires python 3.10-3.12. works on macOS arm64 via coreml. gpu not required for inference (cpu mode works, ~100ms per face).
- **face_recognition (dlib-based)**: lighter but lower accuracy. python 3.12 compat uncertain.
- **arcface via onnx**: good middle ground. single onnx file, no heavy ml framework.

**recommendation**: arcface via onnx runtime. single dependency (onnxruntime), works cross-platform, <50mb model download. trade accuracy for deployment simplicity.

**1b. versioning**

```sql
CREATE TABLE character_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    definition TEXT NOT NULL,  -- full json: prompts, loras, image paths, embeddings
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);
```

each character update creates a new version row. `characters.current_version` points to latest.

**1c. character gallery**

```sql
CREATE TABLE character_gallery (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    character_id TEXT NOT NULL,
    image_path TEXT NOT NULL,
    generation_params TEXT NOT NULL,  -- json: prompt, lora, seed, workflow, backend
    created_at TEXT DEFAULT (datetime('now')),
    FOREIGN KEY (character_id) REFERENCES characters(id)
);
```

auto-populated: every generation tagged with a character_id creates a gallery entry.

**1d. tags and categories**

```sql
ALTER TABLE characters ADD COLUMN tags TEXT;     -- json array of strings
ALTER TABLE characters ADD COLUMN category TEXT; -- "realistic", "anime", "oc", "companion"
```

### phase 2 — multi-backend support

**2a. abstract backend interface**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional

@dataclass
class ImageRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    seed: Optional[int] = None
    character_id: Optional[str] = None
    reference_images: list[str] = []
    lora: Optional[str] = None

@dataclass
class ImageResult:
    file_path: str
    backend: str
    duration_seconds: float
    seed: int
    params: dict

class ImageBackend(ABC):
    @abstractmethod
    async def generate(self, request: ImageRequest) -> ImageResult: ...
    
    @abstractmethod
    async def is_available(self) -> bool: ...
    
    @property
    @abstractmethod
    def name(self) -> str: ...

# implementations
class ComfyUIBackend(ImageBackend): ...  # existing logic, ported to async
class StabilityAIBackend(ImageBackend): ...  # cloud fallback
class DALLEBackend(ImageBackend): ...       # cloud fallback
```

**2b. fallback chain**

```python
class ImageRouter:
    def __init__(self, backends: list[ImageBackend]):
        self._backends = backends
    
    async def generate(self, request: ImageRequest) -> ImageResult:
        for backend in self._backends:
            if await backend.is_available():
                try:
                    return await backend.generate(request)
                except Exception as e:
                    logger.warning(f"backend {backend.name} failed: {e}")
                    continue
        raise AllBackendsFailed(request)
```

comfyui is primary (local-first). stability ai is cloud fallback. dalle is tertiary. user can override ordering per request.

### phase 3 — workflow template validation

**3a. typed schemas (pydantic)**

```python
from pydantic import BaseModel

class Text2ImgTemplate(BaseModel):
    type: str = "text2img"
    positive: str
    negative: str = ""
    steps: int = 20
    cfg: float = 7.0
    sampler: str = "euler"
    scheduler: str = "normal"
    width: int = 512
    height: int = 512

class Img2ImgTemplate(Text2ImgTemplate):
    type: str = "img2img"
    denoise: float = 0.75
    reference_image: str  # path to reference image
```

validate on load — reject mismatched templates with specific error messages.

**3b. template versioning**

store templates in files with versioned names: `text2img-v2.json`, `img2img-v1.json`. allow rollback. template registry tracks active version per type.

**cut from v2**: template marketplace/library, custom template builder ui. these are product features, not technical infrastructure. defer to v3+.

### phase 4 — output management

**4a. image gallery view** (built in phase 0, enriched here)
- browse all generations, filter by character/workflow/date/backend
- lazy loading for performance (sqlite with cursor-based pagination)
- thumbnail generation via comfyui or pil

**4b. image detail view** (built in phase 0, enriched here)
- show all generation parameters (prompt, negative, lora, seed, workflow, backend, duration)
- "regenerate with changes" — pre-fills the image studio with the original parameters, user modifies and regenerates
- "refine" — sends image through img2img with the same character reference

**4c. image collections** (v3, out of scope here)

### phase 5 — job queue improvements

**5a. priority**

```sql
ALTER TABLE image_jobs ADD COLUMN priority INTEGER DEFAULT 0;  -- higher = sooner
```

interactive generations get priority 10. background batch gets priority 0. runner processes highest priority first.

**5b. retry with exponential backoff**

```python
MAX_RETRIES = 3
BASE_DELAY = 5  # seconds

async def run_with_retry(job: ImageJob) -> ImageResult:
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return await backend.generate(job.request)
        except TransientError as e:
            if attempt == MAX_RETRIES:
                raise
            delay = BASE_DELAY * (2 ** (attempt - 1))
            await asyncio.sleep(delay)
```

only retry transient failures (connection refused, timeout, oom). permanent failures (invalid prompt, missing model) fail immediately.

**5c. job scheduling**

```sql
ALTER TABLE image_jobs ADD COLUMN scheduled_at TEXT;  -- iso timestamp, nullable
```

scheduled jobs are created with `scheduled_at` in the future. runner only picks them up after the scheduled time.

### phase 6 — cross-system integration

**6a. builder integration**

builder can generate images as sub-tasks:

```python
# in builder_runner.py, a sub-task of type "generate_image"
async def execute_image_subtask(ctx: RunnerContext) -> ImageResult:
    request = ImageRequest(
        prompt=ctx.initiative.image_prompt,
        character_id=ctx.initiative.image_character,
    )
    return await image_router.generate(request)
```

**6b. companion consistency**

characters in the image store can be linked to the companion personality. a companion with a visual identity has a `character_id` field pointing to an image character. generated images of the companion reference the same character definition.

**6c. memory privacy**

apply memory_policy.py's privacy gate pattern to image generation: generated images tagged with a character_id inherit that character's privacy settings. private characters' images are excluded from gallery unless user explicitly requests them.

---

## not recommended

- **replacing comfyui.** comfyui is mature, local, and extensible. add backends don't replace.
- **video generation.** consistent character video is a different infrastructure problem. defer to v3+.
- **template marketplace / custom template builder.** product features, not technical infrastructure. cut from v2.
- **cloud-only features.** kitty is local-first. cloud backends (stability ai, dalle) are fallbacks, never primary.

---

## migration path (reordered — frontend first)

| week | deliverable |
|------|------------|
| 1-2 | **frontend decoupling** — independent `/images` routes, gallery and detail views, remove image code from page.tsx |
| 3-5 | **character store v2** — reference images, arcface embeddings, versioning, character gallery, tags/categories |
| 6-7 | **multi-backend** — abstract interface, port comfyui to async, stability ai backend |
| 8 | **workflow template validation** — pydantic schemas, type-safe loading, versioned templates |
| 9 | **job queue** — priority, retry with backoff, scheduling |
| 10 | **cross-system** — builder integration, companion consistency link, privacy gate for images |

range: 10 weeks. frontend decoupling first prevents building features into the monolith.

---

## cross-references to other audit documents

- `architecture-honesty.md`: image systems are functional basic, oversold advanced. v1 character store is honest. backend is single-provider. the biggest blocker is frontend monolith coupling.
- `kittybuilder-redesign.md`: builder should generate images as sub-tasks (phase 6). image job queue and builder queue are separate — unification is out of scope for v2.
- `kitty-vision-gap-analysis.md`: character consistency is p2. creative modalities beyond text+image are p3. cross-modal integration is p3.
- `repo-landscape.md`: no external project combines companion identity + character-consistent image generation. kitty's integration is novel.