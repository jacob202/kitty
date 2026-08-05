from __future__ import annotations

from copy import deepcopy

import pytest

from gateway.model_policy_alignment import validate_model_role_alignment
from gateway.operating_policy import OperatingPolicyError, load_model_policy


def _routing() -> dict:
    return {
        "readable": True,
        "error": None,
        "routes": [
            {
                "alias": "kitty-default",
                "provider": "openrouter",
                "upstream_model": "deepseek/deepseek-v4-pro",
            },
            {
                "alias": "kitty-small",
                "provider": "openrouter",
                "upstream_model": "deepseek/deepseek-v4-flash",
            },
            {
                "alias": "kitty-think",
                "provider": "openrouter",
                "upstream_model": "qwen/qwen3-235b-a22b-thinking-2507",
            },
            {
                "alias": "kitty-code",
                "provider": "openrouter",
                "upstream_model": "qwen/qwen3-coder",
            },
            {
                "alias": "kitty-vision",
                "provider": "openrouter",
                "upstream_model": "mistralai/mistral-small-3.2-24b-instruct",
            },
        ],
    }


def test_checked_in_model_policy_matches_the_live_litellm_config():
    result = validate_model_role_alignment()

    assert result["status"] == "aligned"
    assert {row["role"] for row in result["roles"]} == {
        "auto",
        "fast",
        "think",
        "code",
        "vision",
    }


def test_route_change_requires_the_policy_and_evaluation_record_to_change_too():
    routing = deepcopy(_routing())
    code = next(row for row in routing["routes"] if row["alias"] == "kitty-code")
    code["upstream_model"] = "some/new-coder"

    with pytest.raises(OperatingPolicyError, match="policy expects"):
        validate_model_role_alignment(
            policy=load_model_policy(),
            routing=routing,
        )


def test_missing_route_fails_instead_of_hiding_the_mode():
    routing = deepcopy(_routing())
    routing["routes"] = [
        row for row in routing["routes"] if row["alias"] != "kitty-vision"
    ]

    with pytest.raises(OperatingPolicyError, match="absent from LiteLLM"):
        validate_model_role_alignment(
            policy=load_model_policy(),
            routing=routing,
        )
