"""Mock-transport tests for the hosted FLUX.2 (BFL Direct) lane (IL-04).

Covers packet cases A–L:
  A. draft chooses exact Klein 4B target
  B. final chooses exact Pro target
  C. txt2img reaches the correct current FLUX.2 endpoint
  D. edit uses the same FLUX.2 family with a reference (no Kontext model)
  E. references preserve compiler ordering exactly
  F. BFL status/refusal/error produces a typed/loud terminal job state
  G. output is downloaded immediately and persisted
  H. provider cost reconciles against the same target used for estimate
  I. unknown target/model refuses before spend
  J. private_adult causes zero BFL calls
  K. BFL unavailable causes no silent fallback
  L. legacy direct path cannot bypass compiler provenance for FLUX.2 routes
"""

from __future__ import annotations

import json as _json
from pathlib import Path
from types import SimpleNamespace

import pytest

from gateway import (
    flux2_compiler,
    flux2_targets,
    image_jobs,
    image_policy,
    image_recipes,
    image_sessions,
)
from gateway.flux2_compiler import (
    OPERATION_IMG2IMG,
    CompiledFlux2Request,
    CompiledReference,
    compile_flux2_request,
)
from gateway.flux2_targets import (
    FLUX2_HOSTED_TARGETS,
    FLUX2_KLEIN_4B_H,
    FLUX2_PRO_H,
    Flux2TargetError,
    resolve_flux2_target,
)
from gateway.image_runner import ImageRunnerError, JobResult, run
from gateway.routes import extended


@pytest.fixture(autouse=True)
def _scratch_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import gateway.paths as paths

    monkeypatch.setattr(paths, "KITTY_DB_FILE", tmp_path / "kitty.db")
    monkeypatch.setenv("KITTY_IMAGE_PAID_ENABLED", "1")
    monkeypatch.setenv("BFL_API_KEY", "test-bfl-key")


def _klein_compiled(operation: str = "txt2img", **kw) -> CompiledFlux2Request:
    kw.setdefault("quality_tier", "fast")
    return compile_flux2_request("a nordic wolf in a snowy pine forest at blue hour",
                                 operation=operation, **kw)


def _pro_compiled(**kw) -> CompiledFlux2Request:
    kw.setdefault("quality_tier", "quality")
    return compile_flux2_request("a studio portrait of an astronaut", **kw)


class _FakeClient:
    """In-memory stand-in for httpx.AsyncClient used by _run_flux2."""

    def __init__(self, submit_json, poll_json, sample_bytes=b"fake-png-bytes",
                 *, submit_status=200, poll_status=200):
        self.submit_json = submit_json
        self.poll_json = poll_json
        self.sample_bytes = sample_bytes
        self.submit_status = submit_status
        self.poll_status = poll_status
        self.posted_url = None
        self.posted_headers = None
        self.posted_payload = None
        self.get_urls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def post(self, url, *, headers=None, json=None):
        self.posted_url = url
        self.posted_headers = headers
        self.posted_payload = json
        resp = SimpleNamespace()
        resp.status_code = self.submit_status
        resp.text = _json.dumps(self.submit_json)
        resp.json = lambda: self.submit_json
        return resp

    async def get(self, url, *, headers=None):
        self.get_urls.append(url)
        resp = SimpleNamespace()
        if url == self.submit_json.get("polling_url"):
            resp.status_code = self.poll_status
            resp.text = _json.dumps(self.poll_json)
            resp.json = lambda: self.poll_json
            resp.raise_for_status = lambda: None
            return resp
        resp.status_code = 200
        resp.text = ""
        resp.json = lambda: {}
        resp.content = self.sample_bytes
        resp.raise_for_status = lambda: None
        return resp


class TestTargetResolution:
    def test_draft_chooses_exact_klein_4b_target(self):
        target = resolve_flux2_target(FLUX2_KLEIN_4B_H.target_id)
        assert target == FLUX2_KLEIN_4B_H
        assert target.model_id == "flux-2-klein-4b"
        assert target.quality_tier == "draft"
        assert target.hosted is True
        assert target.reference_limit == 4

    def test_final_chooses_exact_pro_target(self):
        target = resolve_flux2_target(FLUX2_PRO_H.target_id)
        assert target == FLUX2_PRO_H
        assert target.model_id == "flux-2-pro"
        assert target.quality_tier == "final"
        assert target.hosted is True
        assert target.reference_limit == 8

    def test_quality_tier_maps_to_hosted_targets(self):
        assert flux2_targets.flux2_target_for_quality_tier("fast") == FLUX2_KLEIN_4B_H
        assert flux2_targets.flux2_target_for_quality_tier("quality") == FLUX2_PRO_H
        assert flux2_targets.flux2_target_for_quality_tier("maximum") == FLUX2_PRO_H

    def test_unknown_target_refuses_before_spend(self):
        with pytest.raises(Flux2TargetError):
            resolve_flux2_target("flux-9-fake")
        assert FLUX2_KLEIN_4B_H.target_id in FLUX2_HOSTED_TARGETS
        assert FLUX2_PRO_H.target_id in FLUX2_HOSTED_TARGETS
        assert FLUX2_KLEIN_4B_H.model_id in FLUX2_HOSTED_TARGETS


class TestKindRouting:
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_draft_routes_to_klein_target(self, monkeypatch):
        captured = {}

        async def fake_run(*args, **kwargs):
            captured["target"] = kwargs.get("flux2_target")
            result = JobResult(job_id="job_x", filename="x.png", engine="flux2")
            result.cost_usd = 0.014
            return result

        monkeypatch.setattr("gateway.image_runner.run", fake_run)
        monkeypatch.setattr(image_sessions, "attach_job", lambda *_: None)

        recipe = SimpleNamespace(
            provider="flux2", recipe_id="bfl_flux2_draft", execution_target="flux2-klein-4b-h",
            default_width=1024, default_height=1024, workflow_template_id=None,
        )
        monkeypatch.setattr(
            image_recipes, "auto_route",
            lambda **_: image_recipes.RoutingDecision(recipe_id="bfl_flux2_draft", recipe=recipe, reason="draft"),
        )
        session = image_sessions.create_session(title="flux2 draft")
        await extended.studio_generate(extended.StudioGenerateRequest(
            prompt="wolf", quality="fast", session_id=session.session_id
        ))
        assert captured["target"].target_id == "flux2-klein-4b-h"

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_final_routes_to_pro_target(self, monkeypatch):
        captured = {}

        async def fake_run(*args, **kwargs):
            captured["target"] = kwargs.get("flux2_target")
            result = JobResult(job_id="job_y", filename="y.png", engine="flux2")
            result.cost_usd = 0.03
            return result

        monkeypatch.setattr("gateway.image_runner.run", fake_run)
        monkeypatch.setattr(image_sessions, "attach_job", lambda *_: None)

        recipe = SimpleNamespace(
            provider="flux2", recipe_id="bfl_flux2_pro", execution_target="flux2-pro-h",
            default_width=1024, default_height=1024, workflow_template_id=None,
        )
        monkeypatch.setattr(
            image_recipes, "auto_route",
            lambda **_: image_recipes.RoutingDecision(recipe_id="bfl_flux2_pro", recipe=recipe, reason="final"),
        )
        session = image_sessions.create_session(title="flux2 final")
        await extended.studio_generate(extended.StudioGenerateRequest(
            prompt="astronaut", quality="quality", session_id=session.session_id
        ))
        assert captured["target"].target_id == "flux2-pro-h"


class TestTxt2ImgEndpoint:
    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_txt2img_reaches_correct_flux2_endpoint(self, monkeypatch, tmp_path):

        submit = {"polling_url": "https://api.bfl.ai/v1/poll/abc", "cost": 1.4}
        ready = {"status": "Ready", "result": {"sample": "https://cdn.bfl.ai/s/1", "seed": 42}}
        client = _FakeClient(submit, ready, b"\x89PNGfake")
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: client)

        compiled = _klein_compiled()
        result = await run("flux2", "ignored", flux2_target=FLUX2_KLEIN_4B_H, compiled_request=compiled)
        assert client.posted_url == FLUX2_KLEIN_4B_H.endpoint
        assert client.posted_payload["prompt"] == compiled.prompt
        assert client.posted_payload["width"] == 1024
        assert client.posted_payload["height"] == 1024

        job = image_jobs.get_job(result.job_id)
        assert job.provider == "flux2"
        assert job.model_id == "flux-2-klein-4b"
        assert job.compiler_version == flux2_compiler.FLUX2_COMPILER_VERSION
        params = _json.loads(job.compiler_params_json)
        assert params["compiler_id"] == "flux2@1"
        assert job.status.value == "succeeded"


class TestEditSameFamily:
    @pytest.mark.asyncio
    async def test_edit_uses_same_flux2_family_with_reference(self, monkeypatch):

        submit = {"polling_url": "https://api.bfl.ai/v1/poll/x", "cost": 1.5}
        ready = {"status": "Ready", "result": {"sample": "https://cdn.bfl.ai/s/2"}}
        client = _FakeClient(submit, ready)
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: client)

        ref = CompiledReference(reference_id="job_anchor", role="anchor", order=1)
        compiled = compile_flux2_request(
            "change the jacket to denim",
            operation=OPERATION_IMG2IMG,
            references=[ref],
        )
        result = await run(
            "flux2", "ignored", flux2_target=FLUX2_PRO_H,
            compiled_request=compiled, reference_bytes=(b"anchor-bytes",),
        )
        assert client.posted_url == FLUX2_PRO_H.endpoint
        assert "input_image" in client.posted_payload
        assert "denoise" not in client.posted_payload
        assert "seedImage" not in client.posted_payload
        assert "flux-kontext" not in client.posted_url
        job = image_jobs.get_job(result.job_id)
        assert job.operation == "img2img"
        assert job.model_id == "flux-2-pro"


class TestReferenceOrdering:
    def test_references_preserve_compiler_ordering_exactly(self):
        from gateway import flux2_transport

        refs = [
            CompiledReference("a", "identity", order=1),
            CompiledReference("b", "outfit", order=2),
        ]
        payload = flux2_transport.serialize_references(
            FLUX2_KLEIN_4B_H, refs, (b"one", b"two")
        )
        assert list(payload) == ["input_image", "input_image_2"]
        assert payload["input_image"] != payload["input_image_2"]
        assert "input_image_3" not in payload

    def test_reference_limit_enforced_loudly(self):
        from gateway import flux2_transport

        refs = [CompiledReference(str(i), "identity", order=i + 1) for i in range(5)]
        with pytest.raises(ValueError):
            flux2_transport.serialize_references(
                FLUX2_KLEIN_4B_H, refs, [b"x"] * 5
            )

    def test_mismatched_bytes_refuses(self):
        from gateway import flux2_transport

        refs = [CompiledReference("a", "identity", order=1)]
        with pytest.raises(ValueError):
            flux2_transport.serialize_references(FLUX2_KLEIN_4B_H, refs, (b"one", b"two"))


class TestFailureModes:
    @pytest.mark.asyncio
    async def test_refusal_typed_loud_terminal_job(self, monkeypatch):

        submit = {"polling_url": "https://api.bfl.ai/v1/poll/r"}
        moderated = {"status": "Request Moderated", "reason": "content policy"}
        client = _FakeClient(submit, moderated)
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: client)

        compiled = _klein_compiled()
        with pytest.raises(ImageRunnerError) as exc:
            await run("flux2", "ignored", flux2_target=FLUX2_KLEIN_4B_H, compiled_request=compiled)
        assert "Request Moderated" in str(exc.value)

        jobs = image_jobs.list_recent(limit=5)
        assert jobs
        failed = jobs[0]
        assert failed.status.value == "failed"
        assert "Request Moderated" in (failed.normalized_error or "")

    @pytest.mark.asyncio
    async def test_polling_timeout_fails_job(self, monkeypatch):

        submit = {"polling_url": "https://api.bfl.ai/v1/poll/t"}
        running = {"status": "Pending"}
        client = _FakeClient(submit, running)
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: client)

        async def _no_sleep(*_args, **_kwargs):
            return None

        monkeypatch.setattr("asyncio.sleep", _no_sleep)

        compiled = _klein_compiled()
        with pytest.raises(TimeoutError):
            await run("flux2", "ignored", flux2_target=FLUX2_KLEIN_4B_H,
                      compiled_request=compiled)
        job = image_jobs.list_recent(limit=1)[0]
        assert job.status.value == "failed"


class TestDownloadPersist:
    @pytest.mark.asyncio
    async def test_output_downloaded_immediately_and_persisted(self, monkeypatch, tmp_path):

        import gateway.paths as paths

        monkeypatch.setattr(paths, "DATA_DIR", tmp_path / "data")
        submit = {"polling_url": "https://api.bfl.ai/v1/poll/d", "cost": 1.4}
        ready = {"status": "Ready", "result": {"sample": "https://cdn.bfl.ai/s/9", "seed": 7}}
        client = _FakeClient(submit, ready, b"\x89PNG\x0d\x0a")
        monkeypatch.setattr("httpx.AsyncClient", lambda *a, **k: client)

        compiled = _klein_compiled()
        result = await run("flux2", "ignored", flux2_target=FLUX2_KLEIN_4B_H, compiled_request=compiled)
        assert client.get_urls[-1] == "https://cdn.bfl.ai/s/9"

        job = image_jobs.get_job(result.job_id)
        assert job.status.value == "succeeded"
        persisted = Path(job.output_path)
        assert persisted.exists()
        assert persisted.read_bytes() == b"\x89PNG\x0d\x0a"
        assert result.cost_usd == pytest.approx(0.014)
        assert result.engine == "flux2"


class TestCostReconciliation:
    def test_estimate_uses_exact_selected_target(self):
        # Exactly 1.0 megapixel so the golden prices are exact:
        # klein 4B $0.014, pro t2i $0.03, pro i2i $0.045.
        klein = FLUX2_KLEIN_4B_H.estimate_cost_usd(1000, 1000, "txt2img")
        pro_t2i = FLUX2_PRO_H.estimate_cost_usd(1000, 1000, "txt2img")
        pro_i2i = FLUX2_PRO_H.estimate_cost_usd(1000, 1000, "img2img")
        assert klein == pytest.approx(0.014)
        assert pro_t2i == pytest.approx(0.03)
        assert pro_i2i == pytest.approx(0.045)

    def test_estimate_rounds_fractional_megapixels_up_like_bfl_billing(self):
        # BFL explicitly bills 1920x1080 (2.07 MP) as 3 MP. Klein 4B is
        # 1.4c first MP + 0.1c for each of the two additional billed MPs.
        assert FLUX2_KLEIN_4B_H.estimate_cost_usd(1920, 1080, "txt2img") == pytest.approx(0.016)
        # For edits the conservative input estimate uses the same 3 MP size.
        assert FLUX2_KLEIN_4B_H.estimate_cost_usd(1920, 1080, "img2img") == pytest.approx(0.019)

    def test_provider_cost_parsed_from_polling_payload(self):
        from gateway import flux2_transport

        assert flux2_transport.parse_cost_usd({"cost": 1.4}) == pytest.approx(0.014)
        assert flux2_transport.parse_cost_usd({"cost": 3.0}) == pytest.approx(0.03)
        assert flux2_transport.parse_cost_usd({}) is None
        assert flux2_transport.parse_cost_usd({"cost": -1}) is None
        assert flux2_transport.parse_cost_usd({"cost": "nan"}) is None

    @pytest.mark.asyncio
    async def test_actual_cost_reconciles_to_same_target(self, monkeypatch):
        session = image_sessions.create_session(title="flux2 cost")
        recipe = SimpleNamespace(
            provider="flux2", recipe_id="bfl_flux2_pro", execution_target="flux2-pro-h",
            default_width=1000, default_height=1000, workflow_template_id=None,
        )
        monkeypatch.setattr(
            image_recipes, "auto_route",
            lambda **_: image_recipes.RoutingDecision(recipe_id="bfl_flux2_pro", recipe=recipe, reason="final"),
        )

        async def fake_run(*args, **kwargs):
            result = JobResult(job_id="job_c", filename="c.png", engine="flux2")
            result.cost_usd = FLUX2_PRO_H.estimate_cost_usd(1000, 1000, "txt2img")
            return result

        monkeypatch.setattr("gateway.image_runner.run", fake_run)
        monkeypatch.setattr(image_sessions, "attach_job", lambda *_: None)

        await extended.studio_generate(extended.StudioGenerateRequest(
            prompt="astronaut", quality="quality", session_id=session.session_id
        ))
        after = image_sessions.require_session(session.session_id)
        assert after.spend_usd == pytest.approx(0.03)


class TestPrivateLane:
    def test_private_adult_refuses_flux2_target(self):
        with pytest.raises(image_policy.PrivateExecutionRequiredError):
            image_policy.validate_image_execution_policy(
                "private_adult", "synthetic", True, "flux2"
            )

    @pytest.mark.asyncio
    async def test_private_adult_route_zero_bfl_calls(self, monkeypatch):
        session = image_sessions.create_session(title="private flux2")
        calls = 0

        async def fake_run_edit(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = JobResult(job_id="job_p", filename="p.png", engine="kitty_worker")
            return result

        monkeypatch.setattr("gateway.image_runner.run_edit", fake_run_edit)
        monkeypatch.setattr("gateway.image_runner.run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("hosted run must not be called")))
        monkeypatch.setattr(image_sessions, "attach_job", lambda *_: None)

        routing_recipe = SimpleNamespace(
            provider="kitty_worker", recipe_id="kitty_worker_edit",
            supports_img2img=True,
        )
        monkeypatch.setattr(
            image_recipes, "auto_route",
            lambda **_: image_recipes.RoutingDecision(
                recipe_id=routing_recipe.recipe_id,
                recipe=routing_recipe,
                reason="private edit",
            ),
        )

        plan = SimpleNamespace(
            session_id=session.session_id, plan_id="plan_priv", status=None,
            operation="img2img", refined_prompt="change the coat",
            character_id=None, recipe_id="bfl_flux2_pro", guidance_tags=[],
            references=[], content_lane="private_adult",
            consent_basis="synthetic", adult_confirmed=True, anchor_job_id="job_anchor",
        )
        monkeypatch.setattr("gateway.image_plans.require_approved_plan", lambda *a, **k: plan)
        monkeypatch.setattr("gateway.image_sessions.list_session_jobs",
                            lambda *a, **k: [SimpleNamespace(job_id="job_anchor")])
        monkeypatch.setattr("gateway.image_jobs.get_job",
                            lambda *a, **k: SimpleNamespace(job_id="job_anchor"))
        monkeypatch.setattr("gateway.image_runner.read_anchor_artifact",
                            lambda *a, **k: (b"anchor", "anchor.png"))

        await extended.studio_generate(extended.StudioGenerateRequest(
            prompt="ignored", plan_id="plan_priv", session_id=session.session_id
        ))
        assert calls == 1


class TestNoFallback:
    @pytest.mark.asyncio
    async def test_bfl_unavailable_no_silent_fallback(self, monkeypatch):
        monkeypatch.delenv("BFL_API_KEY", raising=False)
        from gateway import image_runner

        available, reason = image_runner.flux2_images_available()
        assert available is False
        assert reason

        compiled = _klein_compiled()
        with pytest.raises(ImageRunnerError):
            await run("flux2", "ignored", flux2_target=FLUX2_KLEIN_4B_H,
                      compiled_request=compiled)


class TestLegacyPath:
    def test_engine_flux_keeps_legacy_provenance_null(self, tmp_path):
        # cf. create_job default: legacy engine="flux" jobs have no compiler provenance.
        from gateway import image_runner

        job = image_jobs.create_job(provider="flux", operation="txt2img", prompt="old")
        assert job.compiler_version is None
        assert job.compiler_params_json is None
        assert "flux" in image_runner.ENGINES
        assert "flux2" in image_runner.ENGINES

    @pytest.mark.asyncio
    async def test_flux2_route_cannot_bypass_compiler_provenance(self):
        with pytest.raises(ImageRunnerError):
            await run("flux2", "ignored")
