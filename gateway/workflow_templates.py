"""Workflow template validation with pydantic schemas.

Workflow templates define the node graph structure for image generation.
Each template specifies required node types, node connections, and parameter
ranges. This module validates that a workflow dict conforms to its template.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, field_validator, model_validator


class WorkflowNodeParam(BaseModel):
    key: str
    type: str = "string"
    required: bool = True
    default: Any = None
    min_value: float | None = None
    max_value: float | None = None


class WorkflowNodeType(BaseModel):
    node_type: str
    required: bool = True
    count_min: int = Field(default=0, ge=0)
    count_max: int = Field(default=1, ge=1)
    params: list[WorkflowNodeParam] = []


class WorkflowTemplate(BaseModel):
    template_id: str
    name: str
    description: str = ""
    provider: str = "comfyui"
    model_family: str = "sdxl"
    default_width: int = Field(default=1024, ge=64, le=4096)
    default_height: int = Field(default=1024, ge=64, le=4096)
    min_steps: int = Field(default=1, ge=1, le=150)
    max_steps: int = Field(default=50, ge=1, le=150)
    min_cfg: float = Field(default=1.0, ge=1.0, le=30.0)
    max_cfg: float = Field(default=30.0, ge=1.0, le=30.0)
    supported_samplers: list[str] = []
    supported_schedulers: list[str] = []
    node_types: list[WorkflowNodeType] = []
    required_checkpoint: str | None = None
    supported_operations: list[str] = ["txt2img"]

    @field_validator("supported_samplers")
    @classmethod
    def _check_samplers(cls, v: list[str]) -> list[str]:
        known = {"euler", "euler_ancestral", "heun", "dpm_2", "dpm_2_ancestral",
                 "lms", "ddim", "uni_pc", "dpm_fast", "dpm_adaptive",
                 "dpmpp_2s_ancestral", "dpmpp_2m", "dpmpp_sde", "dpmpp_3m_sde"}
        for s in v:
            if s not in known:
                raise ValueError(f"unknown sampler: {s!r}")
        return v

    @model_validator(mode="after")
    def _check_steps_vs_cfg(self) -> WorkflowTemplate:
        if self.max_steps < self.min_steps:
            raise ValueError("max_steps must be >= min_steps")
        if self.max_cfg < self.min_cfg:
            raise ValueError("max_cfg must be >= min_cfg")
        return self


class NodeConnection(BaseModel):
    from_node: str
    from_slot: int = 0
    to_node: str
    to_slot: int = 0


class WorkflowInstance(BaseModel):
    """A concrete workflow graph — validated against a template."""
    template_id: str
    nodes: dict[str, dict[str, Any]]
    connections: list[NodeConnection] = []
    metadata: dict[str, Any] = {}


# ── Built-in template definitions ───────────────────────────────────────────

BUILTIN_TEMPLATES: dict[str, WorkflowTemplate] = {
    "sdxl_photonic": WorkflowTemplate(
        template_id="sdxl_photonic",
        name="SDXL Photonic",
        description="Standard SDXL photorealistic workflow",
        provider="comfyui",
        model_family="sdxl",
        default_width=1024,
        default_height=1024,
        min_steps=4,
        max_steps=30,
        min_cfg=1.0,
        max_cfg=10.0,
        supported_samplers=["euler", "euler_ancestral", "dpmpp_2m", "dpmpp_sde"],
        supported_schedulers=["sgm_uniform", "normal", "karras"],
        node_types=[
            WorkflowNodeType(node_type="CheckpointLoaderSimple", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="CLIPTextEncode", required=True, count_min=2, count_max=2),
            WorkflowNodeType(node_type="EmptyLatentImage", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="KSampler", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="VAEDecode", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="SaveImage", required=True, count_min=1, count_max=1),
        ],
        supported_operations=["txt2img", "variation"],
    ),
    "sd15_basic": WorkflowTemplate(
        template_id="sd15_basic",
        name="SD 1.5 Basic",
        description="Standard SD 1.5 workflow",
        provider="comfyui",
        model_family="sd15",
        default_width=512,
        default_height=512,
        min_steps=1,
        max_steps=50,
        min_cfg=1.0,
        max_cfg=30.0,
        supported_samplers=["euler", "euler_ancestral", "dpmpp_2m"],
        supported_schedulers=["sgm_uniform", "normal", "karras"],
        node_types=[
            WorkflowNodeType(node_type="CheckpointLoaderSimple", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="CLIPTextEncode", required=True, count_min=2, count_max=2),
            WorkflowNodeType(node_type="EmptyLatentImage", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="KSampler", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="VAEDecode", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="SaveImage", required=True, count_min=1, count_max=1),
        ],
        supported_operations=["txt2img", "variation", "img2img"],
        required_checkpoint=None,
    ),
    "pulid_sdxl": WorkflowTemplate(
        template_id="pulid_sdxl",
        name="PuLID SDXL Identity",
        description="Strong identity preservation with PuLID on SDXL",
        provider="comfyui",
        model_family="sdxl",
        default_width=1024,
        default_height=1024,
        min_steps=10,
        max_steps=40,
        min_cfg=2.0,
        max_cfg=12.0,
        supported_samplers=["euler", "dpmpp_2m", "dpmpp_sde"],
        supported_schedulers=["sgm_uniform", "karras"],
        node_types=[
            WorkflowNodeType(node_type="CheckpointLoaderSimple", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="CLIPTextEncode", required=True, count_min=2, count_max=2),
            WorkflowNodeType(node_type="EmptyLatentImage", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="KSampler", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="VAEDecode", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="SaveImage", required=True, count_min=1, count_max=1),
            WorkflowNodeType(node_type="LoadImage", required=True, count_min=1, count_max=1),
        ],
        supported_operations=["txt2img"],
    ),
}


def get_template(template_id: str) -> WorkflowTemplate | None:
    return BUILTIN_TEMPLATES.get(template_id)


def list_templates() -> list[WorkflowTemplate]:
    return list(BUILTIN_TEMPLATES.values())


def validate_workflow(workflow: dict[str, Any], template: WorkflowTemplate) -> list[str]:
    """Validate a workflow dict against a template. Returns list of violations."""
    violations: list[str] = []

    node_type_counts: dict[str, int] = {}
    for node_id, node_data in workflow.items():
        if not isinstance(node_data, dict):
            violations.append(f"node {node_id!r}: value must be a dict")
            continue
        cls = node_data.get("class_type")
        if not isinstance(cls, str):
            violations.append(f"node {node_id!r}: missing or invalid class_type")
            continue
        node_type_counts[cls] = node_type_counts.get(cls, 0) + 1

    for nt in template.node_types:
        count = node_type_counts.get(nt.node_type, 0)
        if nt.required and count < nt.count_min:
            violations.append(
                f"required node type {nt.node_type!r} missing "
                f"(need at least {nt.count_min}, found {count})"
            )
        if count > nt.count_max:
            violations.append(
                f"node type {nt.node_type!r} exceeds max count "
                f"(max {nt.count_max}, found {count})"
            )

    return violations


__all__ = [
    "WorkflowTemplate",
    "WorkflowNodeType",
    "WorkflowNodeParam",
    "NodeConnection",
    "WorkflowInstance",
    "BUILTIN_TEMPLATES",
    "get_template",
    "list_templates",
    "validate_workflow",
]
