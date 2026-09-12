from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from gateway.local_review import (
    LocalLlamaServer,
    ReviewExecutionLock,
    ReviewFocus,
    build_llama_server_command,
    build_requirement_prompt,
    detect_risk_tags,
    model_family,
    parse_requirement_answer,
    review_decision,
    run_local_review,
)


def test_requirement_prompt_is_neutral_and_single_purpose() -> None:
    prompt = build_requirement_prompt("The update is atomic.", "candidate code")
    lowered = prompt.lower()
    assert "satisfies the single stated requirement" in lowered
    assert "answer exactly one token" in lowered
    assert "find bugs" not in lowered
    assert "strict reviewer" not in lowered
    assert "propose a fix" not in lowered


def test_parser_fails_closed_on_verbose_or_invalid_answers() -> None:
    assert parse_requirement_answer("YES") == "YES"
    assert parse_requirement_answer(" no \n") == "NO"
    assert parse_requirement_answer("UNSURE") == "UNSURE"
    assert parse_requirement_answer("YES because it looks fine") is None
    assert parse_requirement_answer("") is None


def test_low_risk_review_is_advisory_clear_only_when_every_requirement_is_yes() -> None:
    answers = iter(["YES", "YES"])
    result = review_decision(
        requirements=["A is true", "B is true"],
        candidate="candidate",
        ask=lambda _requirement, _candidate: next(answers),
        implementation_model="deepseek-v4",
        reviewer_model="qwen3.5-9b",
    )
    assert result["decision"] == "advisory_clear"
    assert result["authoritative"] is False
    assert [item["answer"] for item in result["requirements"]] == ["YES", "YES"]


def test_no_unsure_or_malformed_answer_escalates_instead_of_blocking() -> None:
    for answer in ("NO", "UNSURE", "NO because broken"):
        result = review_decision(
            requirements=["A is true"],
            candidate="candidate",
            ask=lambda _requirement, _candidate, answer=answer: answer,
            implementation_model="deepseek-v4",
            reviewer_model="qwen3.5-9b",
        )
        assert result["decision"] == "escalate"
        assert result["requirements"][0]["answer"] in {"NO", "UNSURE", None}


def test_high_risk_requirements_escalate_without_calling_model() -> None:
    called = False

    def ask(_requirement: str, _candidate: str) -> str:
        nonlocal called
        called = True
        return "YES"

    result = review_decision(
        requirements=["Release the payment reservation before any provider call can fail."],
        candidate="candidate",
        ask=ask,
        implementation_model="deepseek-v4",
        reviewer_model="qwen3.5-9b",
    )
    assert result["decision"] == "escalate"
    assert "spend" in result["risk_tags"]
    assert called is False


def test_durable_state_requirements_escalate_before_local_inference() -> None:
    for requirement, tag in (
        ("A backup restore is atomic.", "data_integrity"),
        ("The database migration preserves state.", "data_integrity"),
        ("The concurrent update cannot interleave.", "concurrency"),
    ):
        assert tag in detect_risk_tags([requirement])

    called = False

    def ask(_requirement: str, _candidate: str) -> str:
        nonlocal called
        called = True
        return "YES"

    result = review_decision(
        requirements=["The snapshot import is atomic and preserves data."],
        candidate="candidate",
        ask=ask,
        implementation_model="deepseek-v4",
        reviewer_model="qwen3.5-9b",
    )
    assert result["decision"] == "escalate"
    assert result["reason"] == "high_risk_requires_strong_review"
    assert "data_integrity" in result["risk_tags"]
    assert called is False


def test_explicit_high_risk_tags_and_same_model_family_escalate() -> None:
    assert detect_risk_tags(["Rotate an API credential safely."]) == {"auth_security"}
    assert model_family("openrouter/qwen/qwen3.5-coder") == "qwen"
    assert model_family("deepseek-v4") == "deepseek"

    result = review_decision(
        requirements=["The parser preserves every valid row."],
        candidate="candidate",
        ask=lambda _requirement, _candidate: "YES",
        explicit_risk_tags=["irreversible_external_effect"],
        implementation_model="qwen3.5-coder",
        reviewer_model="Qwen3.5-9B-Q3_K_M",
    )
    assert result["decision"] == "escalate"
    assert "irreversible_external_effect" in result["risk_tags"]

    same_family = review_decision(
        requirements=["The parser preserves every valid row."],
        candidate="candidate",
        ask=lambda _requirement, _candidate: "YES",
        implementation_model="qwen3.5-coder",
        reviewer_model="Qwen3.5-9B-Q3_K_M",
    )
    assert same_family["decision"] == "escalate"
    assert same_family["reason"] == "reviewer_not_model_family_independent"


def test_llama_server_command_uses_verified_low_memory_settings(tmp_path) -> None:
    model = tmp_path / "reviewer.gguf"
    model.write_bytes(b"x")
    command = build_llama_server_command(model, port=18080)
    joined = " ".join(command)
    assert "--no-mmproj" in command
    assert "-np 1" in joined
    assert "-c 2048" in joined
    assert "-b 128" in joined
    assert "-ub 64" in joined
    assert "-fa on" in joined
    assert "-ctk q4_0" in joined
    assert "-ctv q4_0" in joined
    assert "--reasoning off" in joined
    assert "--reasoning-budget 0" in joined
    assert "-ngl 999" in joined
    assert "--host 127.0.0.1" in joined
    assert "--port 18080" in joined


def test_llama_server_command_can_pin_verified_executable(tmp_path: Path) -> None:
    model = tmp_path / "reviewer.gguf"
    model.write_bytes(b"x")
    executable = tmp_path / "llama-server"
    executable.write_bytes(b"runtime")

    command = build_llama_server_command(
        model, port=18080, executable_path=executable
    )

    assert command[0] == str(executable.resolve())


def test_cpu_shadow_runtime_profile_is_explicit_and_fingerprinted(tmp_path: Path) -> None:
    model = tmp_path / "reviewer.gguf"
    model.write_bytes(b"profile-test-model")

    metal = build_llama_server_command(
        model, port=18080, runtime_profile="metal_calibrated_v1"
    )
    cpu = build_llama_server_command(
        model, port=18081, runtime_profile="cpu_shadow_v1"
    )
    assert metal[metal.index("-ngl") + 1] == "999"
    assert cpu[cpu.index("-ngl") + 1] == "0"

    from gateway.local_review import reviewer_fingerprint

    metal_fp = reviewer_fingerprint(
        model, "Qwen3.5-9B-Q3_K_M", runtime_profile="metal_calibrated_v1"
    )
    cpu_fp = reviewer_fingerprint(
        model, "Qwen3.5-9B-Q3_K_M", runtime_profile="cpu_shadow_v1"
    )
    assert metal_fp["runtime_profile"] == "metal_calibrated_v1"
    assert cpu_fp["runtime_profile"] == "cpu_shadow_v1"
    assert metal_fp["inference_flags"] != cpu_fp["inference_flags"]
    assert "-ngl 999" in metal_fp["inference_flags"]
    assert "-ngl 0" in cpu_fp["inference_flags"]
    assert metal_fp["request_timeout_s"] == "45"
    assert cpu_fp["request_timeout_s"] == "120"

    metal_server = LocalLlamaServer(model, runtime_profile="metal_calibrated_v1")
    cpu_server = LocalLlamaServer(model, runtime_profile="cpu_shadow_v1")
    assert metal_server.request_timeout == 45.0
    assert cpu_server.request_timeout == 120.0


def test_cpu_shadow_profile_pins_calibrated_model_and_llama_runtime() -> None:
    import gateway.local_review as local_review

    assert getattr(local_review, "CPU_SHADOW_MODEL_SHA256", None) == (
        "8fed90306e4f019e2bf35f3766470b7bc59ea1a9dae00f5ceb20b43cb5514393"
    )
    assert getattr(local_review, "CPU_SHADOW_LLAMA_SERVER_SHA256", None) == (
        "8939a1cf8a4e9a5cc18d6cd4d2d55440b48f8a44db00abe459a28d837ea051f7"
    )
    assert getattr(local_review, "CPU_SHADOW_LLAMA_SERVER_VERSION", None) == (
        "version: 0.4.0 (build 10809, commit 5266f24da)"
    )


def test_cpu_shadow_profile_rejects_unpinned_model_before_inference(tmp_path: Path) -> None:
    model = tmp_path / "Qwen3.5-9B-Q3_K_M.gguf"
    model.write_bytes(b"wrong-model-bytes")

    result = run_local_review(
        {
            "requirements": ["The parser preserves valid rows."],
            "candidate": "candidate",
            "implementation_model": "deepseek-v4",
        },
        model_path=model,
        use_focus=False,
        runtime_profile="cpu_shadow_v1",
    )

    assert result["decision"] == "escalate"
    assert result["reason"] == "local_reviewer_runtime_error"
    assert "calibrated model SHA-256" in result["error"]


def test_cpu_shadow_profile_rejects_unpinned_llama_binary_before_inference(
    tmp_path: Path,
) -> None:
    import gateway.local_review as local_review

    model = tmp_path / "Qwen3.5-9B-Q3_K_M.gguf"
    model.write_bytes(b"stand-in-calibrated-model")
    fake_llama = tmp_path / "llama-server"
    fake_llama.write_bytes(b"wrong-runtime-binary")
    expected_model_sha = hashlib.sha256(model.read_bytes()).hexdigest()

    class FakeQwenServer:
        model_id = "Qwen3.5-9B-Q3_K_M"

        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ask(self, _requirement: str, _candidate: str) -> str:
            return "YES"

        def fingerprint(self) -> dict[str, str]:
            return {}

    with (
        patch.object(local_review, "CPU_SHADOW_MODEL_SHA256", expected_model_sha, create=True),
        patch("gateway.local_review.shutil.which", return_value=str(fake_llama)),
        patch("gateway.local_review.LocalLlamaServer", FakeQwenServer),
    ):
        result = run_local_review(
            {
                "requirements": ["The parser preserves valid rows."],
                "candidate": "candidate",
                "implementation_model": "deepseek-v4",
            },
            model_path=model,
            use_focus=False,
            runtime_profile="cpu_shadow_v1",
        )

    assert result["decision"] == "escalate"
    assert result["reason"] == "local_reviewer_runtime_error"
    assert "calibrated llama-server SHA-256" in result["error"]


def test_cpu_shadow_profile_executes_the_verified_runtime_path(tmp_path: Path) -> None:
    import gateway.local_review as local_review

    model = tmp_path / "Qwen3.5-9B-Q3_K_M.gguf"
    model.write_bytes(b"stand-in-calibrated-model")
    fake_llama = tmp_path / "llama-server"
    fake_llama.write_bytes(b"stand-in-calibrated-runtime")
    model_sha = hashlib.sha256(model.read_bytes()).hexdigest()
    runtime_sha = hashlib.sha256(fake_llama.read_bytes()).hexdigest()
    seen_executables: list[Path | None] = []

    class FakeQwenServer:
        model_id = "Qwen3.5-9B-Q3_K_M"

        def __init__(self, *args, executable_path=None, **kwargs) -> None:
            seen_executables.append(executable_path)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ask(self, _requirement: str, _candidate: str) -> str:
            return "YES"

    with (
        patch.object(local_review, "CPU_SHADOW_MODEL_SHA256", model_sha),
        patch.object(local_review, "CPU_SHADOW_LLAMA_SERVER_SHA256", runtime_sha),
        patch("gateway.local_review.shutil.which", return_value=str(fake_llama)),
        patch("gateway.local_review.LocalLlamaServer", FakeQwenServer),
    ):
        result = run_local_review(
            {
                "requirements": ["The parser preserves valid rows."],
                "candidate": "candidate",
                "implementation_model": "deepseek-v4",
            },
            model_path=model,
            use_focus=False,
            runtime_profile="cpu_shadow_v1",
        )

    assert result["decision"] == "advisory_clear"
    assert seen_executables == [fake_llama.resolve()]


def test_cpu_shadow_profile_receipts_pinned_runtime_without_executing_binary(
    tmp_path: Path,
) -> None:
    import gateway.local_review as local_review

    model = tmp_path / "Qwen3.5-9B-Q3_K_M.gguf"
    model.write_bytes(b"stand-in-calibrated-model")
    fake_llama = tmp_path / "llama-server"
    fake_llama.write_bytes(b"stand-in-calibrated-runtime")
    model_sha = hashlib.sha256(model.read_bytes()).hexdigest()
    runtime_sha = hashlib.sha256(fake_llama.read_bytes()).hexdigest()

    class FakeQwenServer:
        model_id = "Qwen3.5-9B-Q3_K_M"

        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def ask(self, _requirement: str, _candidate: str) -> str:
            return "YES"

    with (
        patch.object(local_review, "CPU_SHADOW_MODEL_SHA256", model_sha),
        patch.object(local_review, "CPU_SHADOW_LLAMA_SERVER_SHA256", runtime_sha),
        patch.object(
            local_review, "CPU_SHADOW_LLAMA_SERVER_VERSION", "test-calibrated-version"
        ),
        patch("gateway.local_review.shutil.which", return_value=str(fake_llama)),
        patch("gateway.local_review.subprocess.run", side_effect=AssertionError("must not execute runtime")),
        patch("gateway.local_review.LocalLlamaServer", FakeQwenServer),
    ):
        result = run_local_review(
            {
                "requirements": ["The parser preserves valid rows."],
                "candidate": "candidate",
                "implementation_model": "deepseek-v4",
            },
            model_path=model,
            use_focus=False,
            runtime_profile="cpu_shadow_v1",
        )

    assert result["decision"] == "advisory_clear"
    fingerprint = result["reviewer_fingerprint"]
    assert fingerprint["model_sha256"] == model_sha
    assert fingerprint["runtime_executable_sha256"] == runtime_sha
    assert fingerprint["runtime_version"] == "test-calibrated-version"


def test_unknown_runtime_profile_is_rejected_before_server_start(tmp_path: Path) -> None:
    model = tmp_path / "reviewer.gguf"
    model.write_bytes(b"x")
    with pytest.raises(ValueError, match="unknown local review runtime profile"):
        build_llama_server_command(model, port=18080, runtime_profile="caller-controlled")


def test_review_focus_unloads_only_generation_models_and_restores_them() -> None:
    calls: list[tuple[str, str, object]] = []

    def request_json(method: str, url: str, payload: object = None) -> dict:
        calls.append((method, url, payload))
        if method == "GET":
            return {
                "models": [
                    {"name": "qwen3.5:4b", "expires_at": "2318-01-01T00:00:00Z"},
                    {"name": "nomic-embed-text:latest", "expires_at": "2318-01-01T00:00:00Z"},
                ]
            }
        return {}

    with ReviewFocus(["http://127.0.0.1:11435"], request_json=request_json, managed_models={"qwen3.5:4b"}) as focus:
        assert [model.model for model in focus.unloaded] == ["qwen3.5:4b"]

    generate_calls = [call for call in calls if call[1].endswith("/api/generate")]
    assert generate_calls[0][2] == {"model": "qwen3.5:4b", "prompt": "", "keep_alive": 0}
    assert generate_calls[-1][2] == {"model": "qwen3.5:4b", "prompt": "", "keep_alive": -1}
    assert all("nomic-embed-text" not in str(call[2]) for call in generate_calls)


def test_review_focus_restores_models_even_when_review_raises() -> None:
    calls: list[tuple[str, str, object]] = []

    def request_json(method: str, url: str, payload: object = None) -> dict:
        calls.append((method, url, payload))
        if method == "GET":
            return {"models": [{"name": "qwen3.5:4b", "expires_at": "2318-01-01T00:00:00Z"}]}
        return {}

    with pytest.raises(RuntimeError, match="boom"):
        with ReviewFocus(["http://127.0.0.1:11435"], request_json=request_json, managed_models={"qwen3.5:4b"}):
            raise RuntimeError("boom")

    restores = [
        payload
        for method, url, payload in calls
        if method == "POST" and url.endswith("/api/generate") and payload and payload.get("keep_alive") == -1
    ]
    assert restores == [{"model": "qwen3.5:4b", "prompt": "", "keep_alive": -1}]


def test_unknown_implementation_model_cannot_receive_local_approval() -> None:
    result = review_decision(
        requirements=["The parser preserves every valid row."],
        candidate="candidate",
        ask=lambda _requirement, _candidate: "YES",
        implementation_model=None,
        reviewer_model="Qwen3.5-9B-Q3_K_M",
    )
    assert result["decision"] == "escalate"
    assert result["reason"] == "implementation_model_unknown"


def test_request_reviewer_label_cannot_override_actual_runtime_identity(tmp_path: Path) -> None:
    model = tmp_path / "Qwen3.5-9B-Q3_K_M.gguf"
    model.write_bytes(b"model")

    seen_profiles: list[str] = []

    class FakeQwenServer:
        model_id = "Qwen3.5-9B-Q3_K_M"
        def __init__(
            self,
            model_path: Path,
            *,
            runtime_profile: str,
            deadline_monotonic=None,
            executable_path=None,
        ) -> None:
            self.model_path = model_path
            seen_profiles.append(runtime_profile)
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def ask(self, _requirement: str, _candidate: str) -> str: return "YES"

    with patch("gateway.local_review.LocalLlamaServer", FakeQwenServer):
        result = run_local_review(
            {"requirements": ["The parser preserves rows."], "candidate": "candidate",
             "implementation_model": "qwen3.5-coder", "reviewer_model": "deepseek-v4",
             "runtime_profile": "cpu_shadow_v1"},
            model_path=model, use_focus=False,
        )
    assert seen_profiles == ["metal_calibrated_v1"]
    assert result["decision"] != "approve"
    assert result["reviewer_model"] == "Qwen3.5-9B-Q3_K_M"


def test_unknown_nonempty_model_alias_cannot_establish_independence() -> None:
    assert model_family("unknown-worker-alias") is None
    result = review_decision(
        requirements=["The parser preserves rows."], candidate="candidate",
        ask=lambda *_: "YES", implementation_model="unknown-worker-alias",
        reviewer_model="Qwen3.5-9B-Q3_K_M",
    )
    assert result["decision"] == "escalate"
    assert result["reason"] == "implementation_model_family_unknown"


def test_local_yes_is_advisory_without_trusted_promotion_gate() -> None:
    result = review_decision(
        requirements=["The output format is correct."],
        candidate="import os\ndef handler(): return dict(os.environ)",
        ask=lambda *_: "YES", implementation_model="gpt-5",
        reviewer_model="Qwen3.5-9B-Q3_K_M", review_kind="privacy-boundary",
    )
    assert result["decision"] == "advisory_clear"
    assert result["authoritative"] is False


def test_focus_entry_failure_restores_models_already_unloaded(tmp_path: Path) -> None:
    calls: list[tuple[str, str, object]] = []
    def request_json(method: str, url: str, payload: object = None) -> dict:
        calls.append((method, url, payload))
        if method == "GET":
            return {"models": [{"name": "model-one"}, {"name": "model-two"}]}
        assert isinstance(payload, dict)
        if payload["model"] == "model-two" and payload["keep_alive"] == 0:
            raise RuntimeError("simulated second unload failure")
        return {}

    focus = ReviewFocus(
        ["http://fake-ollama"], request_json=request_json,
        managed_models={"model-one", "model-two"}, lock_path=tmp_path / "focus.lock",
    )
    with pytest.raises(RuntimeError, match="second unload"):
        with focus:
            raise AssertionError("body must not run")
    restore_payloads = [
        payload for method, url, payload in calls
        if method == "POST" and url.endswith("/api/generate")
        and isinstance(payload, dict) and payload.get("keep_alive") not in {0, None}
    ]
    assert [item["model"] for item in restore_payloads] == ["model-two", "model-one"]


def test_focus_never_unloads_unmanaged_models(tmp_path: Path) -> None:
    calls: list[tuple[str, str, object]] = []
    def request_json(method: str, url: str, payload: object = None) -> dict:
        calls.append((method, url, payload))
        if method == "GET":
            return {"models": [{"name": "kitty-managed"}, {"name": "foreign-active"}]}
        return {}

    with ReviewFocus(
        ["http://fake-ollama"], request_json=request_json,
        managed_models={"kitty-managed"}, lock_path=tmp_path / "focus.lock",
    ):
        pass
    unloads = [
        payload["model"] for method, url, payload in calls
        if method == "POST" and url.endswith("/api/generate")
        and isinstance(payload, dict) and payload.get("keep_alive") == 0
    ]
    assert unloads == ["kitty-managed"]


def test_focus_lock_prevents_two_reviewers_interleaving(tmp_path: Path) -> None:
    lock = tmp_path / "focus.lock"
    def request_json(method: str, _url: str, _payload: object = None) -> dict:
        return {"models": []} if method == "GET" else {}

    with ReviewFocus([], request_json=request_json, managed_models=set(), lock_path=lock):
        with pytest.raises(RuntimeError, match="already active"):
            with ReviewFocus([], request_json=request_json, managed_models=set(), lock_path=lock):
                pass


def test_incomplete_finish_reason_cannot_be_accepted() -> None:
    server = LocalLlamaServer(Path("not-loaded.gguf"), port=18080)
    with patch("gateway.local_review._request_json", side_effect=[
        {"tokens": [1, 2, 3]},
        {"choices": [{"message": {"content": "YES"}, "finish_reason": "length"}]},
    ]):
        with pytest.raises(RuntimeError, match="incomplete"):
            server.ask("The parser preserves rows.", "candidate")


def test_oversized_input_abstains_before_generation() -> None:
    server = LocalLlamaServer(Path("not-loaded.gguf"), port=18080)
    with patch("gateway.local_review._request_json", return_value={"tokens": list(range(1950))}) as request:
        with pytest.raises(RuntimeError, match="too large"):
            server.ask("The parser preserves rows.", "candidate")
    assert request.call_count == 1


def test_default_model_path_prefers_persistent_kitty_model_dir(tmp_path: Path, monkeypatch) -> None:
    home = tmp_path
    model = home / "Library/Application Support/Kitty/models/local-reviewer/Qwen3.5-9B-Q3_K_M.gguf"
    model.parent.mkdir(parents=True)
    model.write_bytes(b"model")
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    from gateway.local_review import find_default_model_path
    assert find_default_model_path() == model


def test_focus_receipt_preserves_unload_history_after_restore(tmp_path: Path) -> None:
    calls: list[tuple[str, str, object]] = []
    def request_json(method: str, url: str, payload: object = None) -> dict:
        calls.append((method, url, payload))
        if method == "GET":
            return {"models": [{"name": "kitty-managed"}]}
        return {}

    focus = ReviewFocus(
        ["http://fake-ollama"], request_json=request_json,
        managed_models={"kitty-managed"}, lock_path=tmp_path / "focus.lock",
    )
    with focus:
        pass
    assert [item.model for item in focus.unloaded_history] == ["kitty-managed"]
    assert focus.pending_restore == []


def test_missing_local_model_fails_closed_as_escalation(tmp_path: Path) -> None:
    result = run_local_review(
        {"requirements": ["The parser preserves rows."], "candidate": "candidate",
         "implementation_model": "deepseek-v4"},
        model_path=tmp_path / "missing.gguf", use_focus=False,
    )
    assert result["decision"] == "escalate"
    assert result["reason"] == "local_reviewer_runtime_error"


@pytest.mark.parametrize(
    ("fail_model", "expected_restores"),
    [("model-one", ["model-one"]), ("model-two", ["model-two", "model-one"]), ("model-three", ["model-three", "model-two", "model-one"])],
)
def test_focus_entry_unwinds_first_middle_and_last_failure(
    tmp_path: Path, fail_model: str, expected_restores: list[str]
) -> None:
    calls: list[tuple[str, str, object]] = []
    def request_json(method: str, url: str, payload: object = None) -> dict:
        calls.append((method, url, payload))
        if method == "GET":
            return {"models": [{"name": name} for name in ("model-one", "model-two", "model-three")]}
        assert isinstance(payload, dict)
        if payload["model"] == fail_model and payload["keep_alive"] == 0:
            raise RuntimeError(f"unload failed: {fail_model}")
        return {}

    focus = ReviewFocus(
        ["http://fake-ollama"], request_json=request_json,
        managed_models={"model-one", "model-two", "model-three"},
        lock_path=tmp_path / "focus.lock",
    )
    with pytest.raises(RuntimeError, match="unload failed"):
        with focus:
            pass
    restores = [
        payload["model"] for method, url, payload in calls
        if method == "POST" and url.endswith("/api/generate")
        and isinstance(payload, dict) and payload.get("keep_alive") not in {0, None}
    ]
    assert restores == expected_restores
    assert focus.pending_restore == []


def test_focus_entry_preserves_original_and_restore_failures(tmp_path: Path) -> None:
    def request_json(method: str, _url: str, payload: object = None) -> dict:
        if method == "GET":
            return {"models": [{"name": "model-one"}, {"name": "model-two"}]}
        assert isinstance(payload, dict)
        if payload["model"] == "model-two" and payload["keep_alive"] == 0:
            raise RuntimeError("second unload failed")
        if payload["model"] == "model-one" and payload["keep_alive"] != 0:
            raise RuntimeError("restore failed")
        return {}

    focus = ReviewFocus(
        ["http://fake-ollama"], request_json=request_json,
        managed_models={"model-one", "model-two"}, lock_path=tmp_path / "focus.lock",
    )
    with pytest.raises(RuntimeError, match="second unload failed.*restore also failed.*restore failed"):
        with focus:
            pass


def test_cli_focus_is_explicit_opt_in() -> None:
    source = Path("gateway/local_review.py").read_text(encoding="utf-8")
    assert '"--focus", action="store_true"' in source
    assert 'use_focus=args.focus' in source
    assert '"--managed-ollama-model", action="append"' in source


def test_ambiguous_unload_timeout_conservatively_restores_original_residency(tmp_path: Path) -> None:
    resident = {"managed"}
    calls: list[dict] = []
    def request_json(method: str, _url: str, payload: object = None) -> dict:
        if method == "GET":
            return {"models": [{"name": name} for name in sorted(resident)]}
        assert isinstance(payload, dict)
        calls.append(payload.copy())
        if payload["keep_alive"] == 0:
            resident.discard(payload["model"])
            raise RuntimeError("transport timed out after unload applied")
        resident.add(payload["model"])
        return {}
    focus = ReviewFocus(["http://fake"], request_json=request_json, managed_models={"managed"}, lock_path=tmp_path / "focus.lock")
    with pytest.raises(RuntimeError, match="timed out"):
        with focus:
            pass
    assert resident == {"managed"}
    assert any(call.get("keep_alive") != 0 for call in calls)
    assert focus.pending_restore == []


def test_model_sha256_hashes_bytes_even_when_filename_looks_content_addressed(tmp_path: Path) -> None:
    from gateway.local_review import _model_sha256
    model = tmp_path / ("a" * 64)
    model.write_bytes(b"not-the-named-digest")
    actual = hashlib.sha256(b"not-the-named-digest").hexdigest()
    assert _model_sha256(model) == actual
    assert _model_sha256(model) != model.name


def test_execution_lock_serializes_review_even_without_focus(tmp_path: Path) -> None:
    model = tmp_path / "Qwen3.5-9B-Q3_K_M.gguf"
    model.write_bytes(b"model")
    lock_path = tmp_path / "review.lock"
    with ReviewExecutionLock(lock_path):
        result = run_local_review(
            {
                "requirements": ["The parser preserves rows."],
                "candidate": "candidate",
                "implementation_model": "deepseek-v4",
            },
            model_path=model,
            use_focus=False,
            focus_lock_path=lock_path,
            runtime_profile="cpu_shadow_v1",
        )
    assert result["decision"] == "escalate"
    assert result["reason"] == "local_reviewer_runtime_error"
    assert "already active" in result["error"]


def test_zero_wall_budget_fails_before_model_start(tmp_path: Path) -> None:
    model = tmp_path / "Qwen3.5-9B-Q3_K_M.gguf"
    model.write_bytes(b"model")
    with pytest.raises(ValueError, match="max_wall_seconds"):
        run_local_review(
            {"requirements": ["safe"], "candidate": "candidate", "implementation_model": "deepseek-v4"},
            model_path=model,
            use_focus=False,
            runtime_profile="cpu_shadow_v1",
            max_wall_seconds=0,
        )
