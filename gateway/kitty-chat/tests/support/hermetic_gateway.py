"""Minimal real Kitty Gateway surface for the browser continuity seam.

Production chat/completion and chat persistence routers stay real. Only ambient
context/runtime discovery is deterministic so the test cannot consult personal
state, local Ollama, or unrelated dashboard integrations.
"""
from __future__ import annotations

from fastapi import FastAPI

import gateway.context_assembler as context_assembler
import gateway.routes.completions as completions
from gateway.auth import BearerAuthMiddleware
from gateway.context_assembler import ContextBundle
from gateway.doctor import Check
from gateway.routes.chats import router as chats_router
from gateway.routes.repairs import _to_repair


async def _hermetic_context(*args, **kwargs) -> ContextBundle:
    return ContextBundle(system="Hermetic Kitty browser continuity test context.")


async def _hermetic_manifest(*, project_id=None) -> dict:
    return {
        "revision": "hermetic-runtime",
        "connections": {"gateway": {"state": "available", "reason": None}},
        "inference": {
            "available_models": {"state": "available", "value": ["kitty-default"]}
        },
        "tools": {"state": "available"},
        "context": {"active_project": {"state": "available", "value": None}},
        "execution": {"builder": {"state": "available", "value": None}},
    }


context_assembler.assemble_context = _hermetic_context
completions.compose_manifest = _hermetic_manifest
completions.compact_runtime_context = lambda manifest: "<kitty_runtime_truth>hermetic</kitty_runtime_truth>"

app = FastAPI(title="Kitty Hermetic Chat Gateway")
app.add_middleware(BearerAuthMiddleware)
app.include_router(chats_router)
app.include_router(completions.router)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/runtime/manifest")
async def runtime_manifest() -> dict[str, object]:
    return await _hermetic_manifest()


@app.get("/models/picker")
async def model_picker() -> dict[str, object]:
    return {
        "schema_version": 1,
        "source": "hermetic-test",
        "discovery": {"state": "available", "reason": None, "checked_at": None},
        "claims": {"role_tags": "heuristic", "alternatives": "cost-screened only"},
        "presets": [
            {
                "role": "auto",
                "label": "Daily Kitty",
                "route": "kitty-default",
                "purpose": "Hermetic browser continuity test.",
                "kind": "router",
                "provider": None,
                "model": None,
                "configured": True,
                "catalogue": None,
                "catalogue_state": "not_applicable",
                "alternatives": [],
            }
        ],
    }


@app.get("/repairs")
async def repairs() -> dict[str, object]:
    checks = [
        Check("FAIL", "env:.env", "missing — copy .env.example to /Users/jacob/kitty/.env"),
        Check("WARN", "env:llm_key", "none of ['OPENAI_API_KEY'] set — models will fail"),
        Check(
            "FAIL",
            "runtime:venv",
            "no venv at /Users/jacob/kitty/venv — run: python3.11 -m venv venv && venv/bin/pip install -r requirements.txt",
        ),
        Check("FAIL", "service:gateway", "unreachable: http://127.0.0.1:8000/health — run: kitty up"),
        Check("WARN", "store:mem0", "memory client request failed with status code 503"),
        Check("WARN", "codegraph:daemon", "daemon index handshake timed out after 30 seconds"),
    ]
    return {
        "ok": False,
        "checks_run": len(checks),
        "issues": len(checks),
        "repairs": [_to_repair(check) for check in checks],
    }
