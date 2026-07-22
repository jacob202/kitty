"""Tests for identity-preserving image generation workflows."""
from __future__ import annotations

import json

from gateway.image_gen import (
    COMFY_IDENTITY_NODES,
    IPADAPTER_MODEL,
    SDXL_PHOTONIC,
    _wf_ipadapter_identity,
    _wf_ipadapter_sdxl,
)


class TestIPAdapterWorkflows:
    def test_builds_ipadapter_balanced(self):
        wf = _wf_ipadapter_sdxl(
            prompt="a person on a rooftop at sunset",
            neg="ugly, deformed",
            w=1024, h=1024,
            steps=8, cfg=4.5,
            ckpt=SDXL_PHOTONIC,
            ref_image_name="char_ref.png",
            identity_weight=0.7,
        )
        assert wf["1"]["class_type"] == "CheckpointLoaderSimple"
        assert wf["2"]["inputs"]["text"] == "a person on a rooftop at sunset"
        assert wf["3"]["inputs"]["text"] == "ugly, deformed"
        assert wf["4"]["inputs"]["width"] == 1024
        assert wf["4"]["inputs"]["height"] == 1024
        assert wf["10"]["class_type"] == "LoadImage"
        assert wf["10"]["inputs"]["image"] == "char_ref.png"
        assert wf["11"]["class_type"] == "IPAdapterModelLoader"
        assert wf["11"]["inputs"]["ipadapter_file"] == IPADAPTER_MODEL
        assert wf["12"]["class_type"] == "IPAdapter"
        assert wf["12"]["inputs"]["weight"] == 0.7
        assert wf["12"]["inputs"]["weight_type"] == "standard"
        assert wf["12"]["inputs"]["model"] == ["1", 0]
        assert wf["12"]["inputs"]["ipadapter"] == ["11", 0]
        assert wf["12"]["inputs"]["image"] == ["10", 0]
        assert wf["5"]["inputs"]["model"] == ["12", 0]
        assert wf["6"]["class_type"] == "VAEDecode"
        assert wf["7"]["class_type"] == "SaveImage"

    def test_builds_ipadapter_creative(self):
        wf = _wf_ipadapter_sdxl(
            prompt="a person", neg="ugly",
            w=1024, h=1024, steps=6, cfg=5.0,
            ckpt=SDXL_PHOTONIC,
            ref_image_name="ref.png",
            identity_weight=0.5,
        )
        assert wf["12"]["inputs"]["weight"] == 0.5

    def test_builds_identity_first(self):
        wf = _wf_ipadapter_identity(
            prompt="a person", neg="ugly",
            w=1024, h=1024, steps=8, cfg=3.0,
            ckpt=SDXL_PHOTONIC,
            ref_image_name="ref.png",
        )
        # Should override to at least 12 steps and 3.5 cfg
        assert wf["5"]["inputs"]["steps"] >= 12
        assert wf["5"]["inputs"]["cfg"] >= 3.5
        assert wf["12"]["inputs"]["weight"] == 0.85

    def test_workflow_is_valid_json(self):
        wf = _wf_ipadapter_sdxl(
            prompt="test", neg="bad",
            w=512, h=512, steps=4, cfg=2.0,
            ckpt="test.safetensors",
            ref_image_name="ref.png",
        )
        encoded = json.dumps(wf, sort_keys=True)
        decoded = json.loads(encoded)
        assert decoded == wf

    def test_all_nodes_connected(self):
        wf = _wf_ipadapter_sdxl(
            prompt="test", neg="bad",
            w=512, h=512, steps=4, cfg=2.0,
            ckpt="test.safetensors",
            ref_image_name="ref.png",
        )
        # Every slot reference [node_id, output_index] must point to an existing node
        node_ids = set(wf)
        for node_id, node in wf.items():
            for input_name, value in node["inputs"].items():
                if isinstance(value, list) and len(value) == 2:
                    ref_node = str(value[0])
                    assert ref_node in node_ids, (
                        f"node {node_id} input {input_name!r} references "
                        f"missing node {ref_node}"
                    )


class TestRequiredNodes:
    def test_identity_nodes_defined(self):
        assert "IPAdapter" in COMFY_IDENTITY_NODES
        assert "IPAdapterModelLoader" in COMFY_IDENTITY_NODES

    def test_required_nodes_include_load_image(self):
        from gateway.image_gen import COMFY_REQUIRED_NODES
        assert "LoadImage" in COMFY_REQUIRED_NODES
