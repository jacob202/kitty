"""Misc Kitty tool routes (reset, troubleshoot, research, etc.)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel, Field

from gateway import honcho, inventory, learning, researcher, reset, tasks, troubleshooter
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

    success = reset.send_nightly_reset()
    return {"status": "sent" if success else "failed"}


@router.post("/troubleshoot")
async def troubleshoot(payload: TroubleshootRequest):

    return {"response": await troubleshooter.initiate_troubleshooting(payload.device, payload.symptom)}


@router.post("/learn")
async def learn(payload: LearnRequest):

    return {"lesson": await learning.generate_knowledge_gate_question(payload.topic)}


@router.post("/inventory/photo")
async def inventory_photo(file: UploadFile = File(...)):
    import tempfile


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

    result = inventory.process_inventory_image(tmp_path)
    Path(tmp_path).unlink(missing_ok=True)
    return {"message": result}


@router.post("/tasks/sync")
async def tasks_sync(payload: TasksSyncRequest):

    success = tasks.sync_next_action(payload.action)
    return {"success": success}


@router.post("/research/deep")
async def deep_research(payload: DeepResearchRequest):

    result = await researcher.deep_dive(payload.topic)
    return {"result": result}


@router.get("/weekly")
async def weekly_mirror():

    return honcho.get_weekly_mirror()
