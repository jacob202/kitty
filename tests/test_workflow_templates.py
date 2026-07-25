"""Tests for workflow template validation with pydantic schemas."""
from __future__ import annotations

import pytest

from gateway.workflow_templates import (
    BUILTIN_TEMPLATES,
    WorkflowNodeType,
    WorkflowTemplate,
    get_template,
    list_templates,
    validate_workflow,
)


class TestWorkflowTemplate:
    def test_builtin_templates_exist(self):
        assert len(BUILTIN_TEMPLATES) >= 3
        assert "sdxl_photonic" in BUILTIN_TEMPLATES
        assert "sd15_basic" in BUILTIN_TEMPLATES
        assert "pulid_sdxl" in BUILTIN_TEMPLATES

    def test_get_template(self):
        tpl = get_template("sdxl_photonic")
        assert tpl is not None
        assert tpl.provider == "comfyui"
        assert tpl.model_family == "sdxl"

    def test_get_template_missing(self):
        assert get_template("nonexistent") is None

    def test_list_templates(self):
        templates = list_templates()
        assert len(templates) == len(BUILTIN_TEMPLATES)

    def test_template_validation(self):
        tpl = WorkflowTemplate(
            template_id="test",
            name="Test",
            provider="comfyui",
            model_family="sdxl",
        )
        assert tpl.min_steps == 1
        assert tpl.max_steps == 50
        assert tpl.default_width == 1024

    def test_template_invalid_sampler(self):
        with pytest.raises(ValueError, match="unknown sampler"):
            WorkflowTemplate(
                template_id="bad",
                name="Bad",
                provider="comfyui",
                model_family="sdxl",
                supported_samplers=["nope_sampler"],
            )

    def test_template_max_steps_lt_min(self):
        with pytest.raises(ValueError, match="max_steps must be >= min_steps"):
            WorkflowTemplate(
                template_id="bad",
                name="Bad",
                provider="comfyui",
                model_family="sdxl",
                min_steps=30,
                max_steps=10,
            )

    def test_template_max_cfg_lt_min(self):
        with pytest.raises(ValueError, match="max_cfg must be >= min_cfg"):
            WorkflowTemplate(
                template_id="bad",
                name="Bad",
                provider="comfyui",
                model_family="sdxl",
                min_cfg=10.0,
                max_cfg=5.0,
            )

    def test_node_type_defaults(self):
        nt = WorkflowNodeType(node_type="KSampler")
        assert nt.required is True
        assert nt.count_min == 0
        assert nt.count_max == 1
        assert nt.params == []


class TestValidateWorkflow:
    def test_valid_sdxl_workflow(self):
        tpl = get_template("sdxl_photonic")
        assert tpl is not None
        workflow = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": "model.safetensors"}},
            "2": {"class_type": "CLIPTextEncode", "inputs": {"text": "prompt", "clip": ["1", 1]}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "neg", "clip": ["1", 1]}},
            "4": {"class_type": "EmptyLatentImage", "inputs": {"width": 1024, "height": 1024}},
            "5": {"class_type": "KSampler", "inputs": {"seed": 42, "steps": 6, "cfg": 1.5, "model": ["1", 0]}},
            "6": {"class_type": "VAEDecode", "inputs": {"samples": ["5", 0]}},
            "7": {"class_type": "SaveImage", "inputs": {"filename_prefix": "test", "images": ["6", 0]}},
        }
        violations = validate_workflow(workflow, tpl)
        assert violations == []

    def test_missing_required_node(self):
        tpl = get_template("sdxl_photonic")
        assert tpl is not None
        workflow = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
        }
        violations = validate_workflow(workflow, tpl)
        assert any("CLIPTextEncode" in v for v in violations)
        assert any("EmptyLatentImage" in v for v in violations)
        assert any("KSampler" in v for v in violations)
        assert any("VAEDecode" in v for v in violations)
        assert any("SaveImage" in v for v in violations)

    def test_too_many_of_node_type(self):
        tpl = get_template("sdxl_photonic")
        assert tpl is not None
        workflow = {
            "1": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "2": {"class_type": "CheckpointLoaderSimple", "inputs": {}},
            "3": {"class_type": "CLIPTextEncode", "inputs": {"text": "p", "clip": ["1", 1]}},
            "4": {"class_type": "CLIPTextEncode", "inputs": {"text": "n", "clip": ["1", 1]}},
            "5": {"class_type": "EmptyLatentImage", "inputs": {}},
            "6": {"class_type": "KSampler", "inputs": {}},
            "7": {"class_type": "VAEDecode", "inputs": {}},
            "8": {"class_type": "SaveImage", "inputs": {}},
        }
        violations = validate_workflow(workflow, tpl)
        assert any("CheckpointLoaderSimple" in v and "exceeds max count" in v for v in violations)
