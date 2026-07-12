"""Misc Kitty tool routes (reset, troubleshoot, research, etc.)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from gateway.constants import MAX_INVENTORY_BYTES

router = APIRouter(tags=["tools"])


class TroubleshootRequest(BaseModel):
    device: str = Field(min_length=1)
    symptom: str = Field(min_length=1)


class TasksSyncRequest(BaseModel):
    action: str


class LearnRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)


class DeepResearchRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=1000)


@router.get("/reset")
async def nightly_reset():
    from gateway.reset import send_nightly_reset

    success = send_nightly_reset()
    return {"status": "sent" if success else "failed"}


@router.post("/troubleshoot")
async def troubleshoot(payload: TroubleshootRequest):
    from gateway.troubleshooter import initiate_troubleshooting

    return {"response": await initiate_troubleshooting(payload.device, payload.symptom)}


@router.post("/learn")
async def learn(payload: LearnRequest):
    from gateway.learning import generate_knowledge_gate_question

    return {"lesson": await generate_knowledge_gate_question(payload.topic)}


@router.post("/inventory/photo")
async def inventory_photo(file: UploadFile = File(...)):
    import tempfile

    from gateway.inventory import process_inventory_image

    written = 0
    chunks: list[bytes] = []
    while chunk := await file.read(64 * 1024):
        written += len(chunk)
        if written > MAX_INVENTORY_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"inventory photo exceeds {MAX_INVENTORY_BYTES} bytes",
            )
        chunks.append(chunk)

    with tempfile.NamedTemporaryFile(
        delete=False, suffix=Path(file.filename or ".jpg").suffix
    ) as tmp:
        tmp.write(b"".join(chunks))
        tmp_path = tmp.name

    result = process_inventory_image(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)
    return {"message": result}


@router.post("/tasks/sync")
async def tasks_sync(payload: TasksSyncRequest):
    from gateway.tasks import sync_next_action

    success = sync_next_action(payload.action)
    return {"success": success}


@router.post("/research/deep")
async def deep_research(payload: DeepResearchRequest):
    from gateway.researcher import deep_dive

    result = await deep_dive(payload.topic)
    return {"result": result}


@router.get("/weekly")
async def weekly_mirror():
    from gateway.honcho import get_weekly_mirror

    return get_weekly_mirror()
