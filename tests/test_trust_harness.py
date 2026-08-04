import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "evals" / "kitty" / "promptfooconfig.json"
MAKEFILE_PATH = ROOT / "Makefile"


def _config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def test_trust_harness_config_is_valid_and_live_gateway_scoped():
    config = _config()

    assert config["$schema"] == "https://promptfoo.dev/config-schema.json"
    assert config["prompts"] == ["{{prompt}}"]

    providers = config["providers"]
    assert len(providers) == 1
    provider = providers[0]
    assert provider["id"] == "http"

    provider_config = provider["config"]
    assert provider_config["url"] == "{{env.KITTY_EVAL_BASE_URL}}/v1/chat/completions"
    assert provider_config["body"]["model"] == "{{env.KITTY_EVAL_MODEL}}"
    assert provider_config["body"]["stream"] is False
    assert provider_config["maxRetries"] == 0
    assert provider_config["validateStatus"] == "status >= 200 && status <= 299"
    assert provider_config["headers"]["Authorization"] == (
        "Bearer {{env.GATEWAY_SECRET}}"
    )


def test_trust_harness_has_bounded_regression_cases():
    tests = _config()["tests"]

    assert len(tests) >= 8
    descriptions = [case["description"] for case in tests]
    assert len(descriptions) == len(set(descriptions))

    for case in tests:
        assert case["description"].strip()
        assert case["vars"]["prompt"].strip()
        assert case["assert"]
        for assertion in case["assert"]:
            assert assertion["type"].strip()


def test_live_eval_make_target_is_cost_guarded_version_pinned_and_authenticated():
    makefile = MAKEFILE_PATH.read_text(encoding="utf-8")

    assert "trust-eval:" in makefile
    assert "KITTY_LIVE_EVAL" in makefile
    assert "promptfoo@0.121.19" in makefile
    assert "--no-cache" in makefile
    assert "KITTY_EVAL_BASE_URL" in makefile
    assert "KITTY_EVAL_MODEL" in makefile
    assert 'curl -fsS "$$BASE_URL/health"' in makefile
    assert "python3.12 -c" in makefile
    assert "GATEWAY_SECRET=\"$$SECRET\"" in makefile
    assert "/proxy/health" not in makefile
