"""Model routing description — the answer to 'which provider am I actually on'."""

from __future__ import annotations

import textwrap

import pytest

from gateway import model_routing


@pytest.fixture
def config(tmp_path, monkeypatch):
    def _write(body: str):
        path = tmp_path / "litellm_config.yaml"
        path.write_text(textwrap.dedent(body))
        monkeypatch.setattr(model_routing, "LITELLM_CONFIG", path)
        return path

    return _write


def test_reports_real_config():
    """The shipped config must be describable, not just the fixtures."""
    result = model_routing.describe_routing()
    assert result["readable"] is True
    aliases = {r["alias"] for r in result["routes"]}
    assert "kitty-default" in aliases


def test_resolve_chat_route_honors_explicit_non_virtual_model():
    decision = model_routing.resolve_chat_route(
        "openai/gpt-4o-mini",
        "explain how recursion works",
        reroute_virtual_models=True,
    )

    assert decision.model == "openai/gpt-4o-mini"
    assert decision.source == "request"


def test_resolve_chat_route_reroutes_virtual_model_by_complexity():
    decision = model_routing.resolve_chat_route(
        "kitty-default",
        "explain how recursion works",
        reroute_virtual_models=True,
    )

    assert decision.model == "kitty-sonnet"
    assert decision.source == "complexity_classifier"
    assert decision.tier == "deep"


def test_resolve_chat_route_normalizes_legacy_alias():
    decision = model_routing.resolve_chat_route(
        "kitty-agent",
        "hello",
        honor_requested_model=True,
        reroute_virtual_models=False,
    )

    assert decision.model == "kitty-default"
    assert decision.requested_model == "kitty-agent"


def test_splits_provider_from_upstream_model(config, monkeypatch):
    config("""
        model_list:
          - model_name: kitty-default
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-pro
              api_key: os.environ/OPENROUTER_API_KEY
    """)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    route = model_routing.describe_routing()["routes"][0]
    assert route["provider"] == "openrouter"
    assert route["upstream_model"] == "deepseek/deepseek-v4-pro"
    assert route["key"] == {"env_var": "OPENROUTER_API_KEY", "present": True, "note": None}


def test_missing_key_is_reported_not_guessed(config, monkeypatch):
    config("""
        model_list:
          - model_name: kitty-default
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-pro
              api_key: os.environ/OPENROUTER_API_KEY
    """)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    result = model_routing.describe_routing()
    assert result["routes"][0]["key"]["present"] is False
    assert any("OPENROUTER_API_KEY is not set" in w for w in result["warnings"])


def test_single_provider_is_flagged_as_a_single_point_of_failure(config, monkeypatch):
    config("""
        model_list:
          - model_name: kitty-default
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-pro
              api_key: os.environ/OPENROUTER_API_KEY
          - model_name: kitty-small
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-flash
              api_key: os.environ/OPENROUTER_API_KEY
    """)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    warnings = model_routing.describe_routing()["warnings"]
    assert any("every model route points at 'openrouter'" in w for w in warnings)


def test_same_provider_fallback_is_flagged(config, monkeypatch):
    config("""
        model_list:
          - model_name: kitty-default
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-pro
              api_key: os.environ/OPENROUTER_API_KEY
          - model_name: kitty-small
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-flash
              api_key: os.environ/OPENROUTER_API_KEY
        litellm_settings:
          fallbacks:
            - kitty-default: [kitty-small]
    """)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")

    result = model_routing.describe_routing()
    assert result["routes"][0]["fallbacks"] == ["kitty-small"]
    assert any("falls back to kitty-small on the same provider" in w for w in result["warnings"])


def test_cross_provider_fallback_is_not_flagged(config, monkeypatch):
    config("""
        model_list:
          - model_name: kitty-default
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-pro
              api_key: os.environ/OPENROUTER_API_KEY
          - model_name: kitty-local
            litellm_params:
              model: openai/mlx-community/whatever
              api_key: os.environ/LOCAL_API_KEY
        litellm_settings:
          fallbacks:
            - kitty-default: [kitty-local]
    """)
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
    monkeypatch.setenv("LOCAL_API_KEY", "local")

    warnings = model_routing.describe_routing()["warnings"]
    assert not any("same provider" in w for w in warnings)
    assert not any("every model route points at" in w for w in warnings)


def test_literal_api_key_is_called_out(config):
    config("""
        model_list:
          - model_name: kitty-default
            litellm_params:
              model: openrouter/deepseek/deepseek-v4-pro
              api_key: sk-hardcoded-secret
    """)

    key = model_routing.describe_routing()["routes"][0]["key"]
    assert key["env_var"] is None
    assert "literal" in key["note"]


def test_missing_config_fails_loud(tmp_path, monkeypatch):
    monkeypatch.setattr(model_routing, "LITELLM_CONFIG", tmp_path / "nope.yaml")

    result = model_routing.describe_routing()
    assert result["readable"] is False
    assert "not found" in result["error"]
    assert result["routes"] == []


def test_invalid_yaml_fails_loud(tmp_path, monkeypatch):
    path = tmp_path / "litellm_config.yaml"
    path.write_text("model_list: [\n  unterminated")
    monkeypatch.setattr(model_routing, "LITELLM_CONFIG", path)

    result = model_routing.describe_routing()
    assert result["readable"] is False
    assert "not valid YAML" in result["error"]


class TestProviderChain:
    """The direct-call fallback chain — the thing 'switch providers' actually means."""

    @pytest.fixture(autouse=True)
    def isolated_prefs(self, tmp_path, monkeypatch):
        from gateway import llm_client, provider_prefs

        monkeypatch.setattr(
            provider_prefs, "PROVIDER_PREFS_FILE", tmp_path / "providers.json"
        )
        monkeypatch.setattr(llm_client, "load_dotenv", lambda *args, **kwargs: False)
        monkeypatch.setattr(llm_client, "dotenv_values", lambda *args, **kwargs: {})

    def test_local_mlx_is_in_the_chain(self):
        names = {p["name"] for p in model_routing.describe_providers()["providers"]}
        assert "local" in names

    def test_local_needs_no_key(self):
        local = next(
            p for p in model_routing.describe_providers()["providers"] if p["name"] == "local"
        )
        assert local["requires_key"] is False
        assert local["configured"] is True

    def test_keyless_cloud_provider_reads_as_unconfigured(self, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

        openrouter = next(
            p
            for p in model_routing.describe_providers()["providers"]
            if p["name"] == "openrouter"
        )
        assert openrouter["configured"] is False

    def test_agentrouter_environment_disable_is_reported_as_disabled(self, monkeypatch):
        monkeypatch.setenv("AGENT_ROUTER_TOKEN", "sk-test")
        monkeypatch.setenv("KITTY_DISABLE_AGENTROUTER", "1")

        agentrouter = next(
            p
            for p in model_routing.describe_providers()["providers"]
            if p["name"] == "agentrouter"
        )
        assert agentrouter["configured"] is True
        assert agentrouter["disabled"] is True

    def test_saved_preference_shows_up_in_the_order(self):
        from gateway.llm_client import PROVIDERS
        from gateway.provider_prefs import save_preferences

        save_preferences(["gemini"], ["agentrouter"], known=tuple(PROVIDERS.keys()))

        described = model_routing.describe_providers()
        assert described["order"][0] == "gemini"
        assert "agentrouter" not in described["order"]

    def test_warns_when_first_choice_has_no_key(self, monkeypatch):
        from gateway.llm_client import PROVIDERS
        from gateway.provider_prefs import save_preferences

        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        save_preferences(["openrouter", "local"], [], known=tuple(PROVIDERS.keys()))

        warnings = model_routing.describe_providers()["warnings"]
        assert any("actually start at 'local'" in w for w in warnings)


class TestLocalDetection:
    def test_local_api_base_beats_the_openai_prefix(self, config, monkeypatch):
        config("""
            model_list:
              - model_name: kitty-local
                litellm_params:
                  model: openai/mlx-community/Qwen3.5-4B-4bit
                  api_base: http://127.0.0.1:8010/v1
        """)

        route = model_routing.describe_routing()["routes"][0]
        assert route["provider"] == "local"

    def test_remote_openai_stays_openai(self, config, monkeypatch):
        config("""
            model_list:
              - model_name: kitty-gpt
                litellm_params:
                  model: openai/gpt-4o-mini
                  api_key: os.environ/OPENAI_API_KEY
        """)
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        route = model_routing.describe_routing()["routes"][0]
        assert route["provider"] == "openai"


# ── the user-facing menu ──────────────────────────────────────────────────────


def test_every_menu_id_resolves_to_a_configured_litellm_route():
    """A menu row that maps to a route litellm has never heard of is a 404 the
    user only discovers by picking it."""
    routes = {
        entry["alias"] for entry in model_routing.describe_routing()["routes"]
    }
    for entry in model_routing.USER_FACING_MODELS:
        assert entry["route"] in routes, f"{entry['id']} -> {entry['route']}"


def test_menu_entries_are_distinct_models():
    """Two rows pointing at the same upstream model is a menu that lies."""
    by_alias = {
        entry["alias"]: entry
        for entry in model_routing.describe_routing()["routes"]
    }
    upstream = [
        by_alias[entry["route"]]["upstream_model"]
        for entry in model_routing.USER_FACING_MODELS
        if entry["id"] != "kitty-auto"  # Auto has no model of its own
    ]
    assert len(set(upstream)) == len(upstream), upstream


def test_auto_hands_the_tier_decision_back_to_kitty():
    decision = model_routing.resolve_chat_route(
        "kitty-auto", "explain how recursion works", reroute_virtual_models=True
    )

    assert decision.source == "complexity_classifier"
    assert decision.model == model_routing.LITELLM_SONNET


def test_a_pinned_menu_choice_is_not_second_guessed():
    """Picking "Kitty Think" for a trivial message must stay on Think.

    Rerouting every ``kitty-*`` id made the menu a suggestion the classifier
    could overrule, which is not what picking a model means.
    """
    decision = model_routing.resolve_chat_route(
        "kitty-think", "hi", reroute_virtual_models=True
    )

    assert decision.source == "request"
    assert decision.model == model_routing.LITELLM_THINK


def test_menu_ids_normalize_onto_litellm_routes():
    normalize = model_routing.normalize_litellm_request_model
    assert normalize("kitty-auto") == model_routing.LITELLM_DEFAULT
    assert normalize("kitty-fast") == model_routing.LITELLM_SMALL
    assert normalize("kitty-code") == model_routing.LITELLM_CODE


def test_auto_routes_an_image_turn_to_vision():
    """An image-only turn reduces to an empty string, so the complexity
    classifier has no modality signal and can only pick a text tier — the upload
    then silently reaches a model that cannot read it."""
    decision = model_routing.resolve_chat_route(
        "kitty-auto", "", reroute_virtual_models=True, has_image=True
    )

    assert decision.model == model_routing.LITELLM_VISION
    assert decision.source == "modality"


def test_auto_honours_the_domain_classification():
    """The route re-classified without the domain the endpoint had already
    computed, so a domain-deep turn was routed as if it were not while telemetry
    still reported deep."""
    with_domain = model_routing.resolve_chat_route(
        "kitty-auto", "I have a fever", reroute_virtual_models=True, domain="health"
    )
    from gateway.reasoning import classify_complexity

    assert with_domain.tier == classify_complexity("I have a fever", domain="health").tier


def test_a_pinned_choice_still_wins_over_an_image():
    decision = model_routing.resolve_chat_route(
        "kitty-code", "fix this", reroute_virtual_models=True, has_image=True
    )

    assert decision.model == model_routing.LITELLM_CODE
    assert decision.source == "request"
