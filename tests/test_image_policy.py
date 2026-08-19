"""IL-02 acceptance: fail-closed content-lane execution policy (ADR 0040 #8).

These tests pin the content-lane contract — `content_lane` in {safe,
private_adult}, `consent_basis` in {synthetic, self} or null, and
`adult_confirmed: bool` — across the durable plan store, the dispatch route,
and the runner boundary. The invariant is that private-adult work can NEVER
reach a hosted provider through routing, fallback, retry, or substitution, and
that prompt keywords grant zero policy authority.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest
from fastapi import HTTPException

from gateway import image_jobs, image_plans
from gateway import image_sessions as sessions
from gateway.image_plan import build_image_plan
from gateway.image_plans import PlanStoreError, persist_plan, require_approved_plan
from gateway.image_policy import (
    AdultConfirmationRequiredError,
    ConsentRequiredError,
    ImagePolicyError,
    PrivateExecutionRequiredError,
    validate_image_execution_policy,
)
from gateway.routes import extended

#: Neutral sentinel prompt: no EXPLICIT_KW is ever a policy signal, so tests
#: deliberately do not rely on keywords to reach the private lane.
SENTINEL_PROMPT = "a portrait study in studio light"


@pytest.fixture(autouse=True)
def _fresh_db(tmp_path: Path):
    test_db = tmp_path / "kitty.db"
    test_db.parent.mkdir(parents=True, exist_ok=True)
    import gateway.paths as gp

    original = gp.KITTY_DB_FILE
    gp.KITTY_DB_FILE = test_db

    conn = sqlite3.connect(str(test_db))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    image_plans._ensure_db(conn)
    conn.commit()
    conn.close()

    yield test_db

    gp.KITTY_DB_FILE = original


def _build_plan(
    *,
    content_lane: str | None = None,
    consent_basis: str | None = None,
    adult_confirmed: bool = False,
):
    return build_image_plan(
        SENTINEL_PROMPT,
        guidance_tags=["text_rendering"],
        content_lane=content_lane,
        consent_basis=consent_basis,
        adult_confirmed=adult_confirmed,
    )


def _succeeded_anchor(tmp_path: Path, *, prompt: str = "a portrait") -> str:
    job = image_jobs.create_job(provider="comfyui", operation="txt2img", prompt=prompt)
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUBMITTED)
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.RUNNING)
    artifact = tmp_path / f"{job.job_id}.png"
    artifact.write_bytes(b"\x89PNG\r\n\x1a\n-fake-source-bytes")
    image_jobs.update_job(
        job.job_id, output_path=str(artifact), artifact_id=f"art_{job.job_id}"
    )
    image_jobs.transition(job.job_id, image_jobs.ImageJobStatus.SUCCEEDED)
    return job.job_id


def _private_session_with_anchor(tmp_path: Path) -> tuple:
    """A session with a succeeded, session-owned anchor for a private edit plan."""
    session = sessions.create_session(title="private lane")
    anchor = _succeeded_anchor(tmp_path)
    sessions.attach_job(session.session_id, anchor)
    sessions.set_anchor(session.session_id, anchor)
    return session, anchor


def _persist_private_plan(
    session,
    anchor: str,
    *,
    consent_basis: str = "synthetic",
    adult_confirmed: bool = True,
):
    return persist_plan(
        session.session_id,
        _build_plan(
            content_lane="private_adult",
            consent_basis=consent_basis,
            adult_confirmed=adult_confirmed,
        ),
        operation="img2img",
        anchor_job_id=anchor,
    )


def _edit_recipe_mock(captured: dict, *, provider: str = "comfyui"):
    def fake_auto_route(**kwargs):
        from gateway.image_recipes import Recipe, RoutingDecision

        captured["route_operation"] = kwargs["operation"]
        recipe = Recipe(
            recipe_id="r_edit",
            display_name="Edit",
            description=None,
            provider=provider,
            workflow_template_id=None,
            model_family=None,
            supports_img2img=True,
        )
        return RoutingDecision(recipe.recipe_id, recipe, "test")

    return fake_auto_route


def _capture_run_edit(monkeypatch, captured: dict):
    async def fake_run_edit(prompt: str, *, anchor_job_id: str, **kwargs):
        captured["run_edit"] = kwargs
        captured["anchor_job_id"] = anchor_job_id
        from gateway.image_runner import JobResult

        job = image_jobs.create_job(
            provider="kitty_worker",
            operation="img2img",
            prompt=prompt,
            parent_id=anchor_job_id,
        )
        return JobResult(
            job_id=job.job_id, filename="/tmp/edit.png", engine="kitty_worker"
        )

    async def fail_run(*_args, **_kwargs):
        raise AssertionError("private work must not reach image_runner.run()")

    monkeypatch.setattr("gateway.image_runner.run_edit", fake_run_edit)
    monkeypatch.setattr("gateway.image_runner.run", fail_run)
    monkeypatch.setattr(
        "gateway.image_recipes.auto_route",
        _edit_recipe_mock(captured, provider="comfyui"),
    )
    return captured


class TestSafeBackcompat:
    """A: safe/null/false round-trips and safe generation keeps working."""

    def test_default_plan_backfills_to_safe_lane(self):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        assert stored.content_lane == "safe"
        assert stored.consent_basis is None
        assert stored.adult_confirmed is False

        resumed = image_plans.require_plan(stored.plan_id)
        assert resumed.content_lane == "safe"
        assert resumed.consent_basis is None
        assert resumed.adult_confirmed is False

    def test_preexisting_row_reads_back_as_safe(self):
        """A pre-IL-02 row (no policy columns) must read as safe, never private."""
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        import gateway.paths as gp

        with sqlite3.connect(gp.KITTY_DB_FILE) as conn:
            conn.execute(
                "UPDATE image_plans SET content_lane = 'safe', consent_basis = NULL,"
                " adult_confirmed = 0 WHERE plan_id = ?",
                (stored.plan_id,),
            )
            conn.commit()
        resumed = image_plans.require_plan(stored.plan_id)
        assert resumed.content_lane == "safe"
        assert resumed.consent_basis is None
        assert resumed.adult_confirmed is False

    @pytest.mark.asyncio
    async def test_safe_plan_dispatches_to_recipe_engine(self, monkeypatch):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        captured: dict = {}

        async def fake_run(engine, prompt, **kwargs):
            captured["engine"] = engine
            captured["policy"] = {
                "content_lane": kwargs["content_lane"],
                "consent_basis": kwargs["consent_basis"],
                "adult_confirmed": kwargs["adult_confirmed"],
            }
            job = image_jobs.create_job(
                provider="comfyui", operation="txt2img", prompt=prompt
            )
            from gateway.image_runner import JobResult

            return JobResult(job_id=job.job_id, filename="/tmp/out.png", engine="comfyui")

        def fake_auto_route(**kwargs):
            from gateway.image_recipes import Recipe, RoutingDecision

            recipe = Recipe(
                recipe_id="r_default",
                display_name="Default",
                description=None,
                provider="comfyui",
                workflow_template_id=None,
                model_family=None,
            )
            return RoutingDecision(recipe.recipe_id, recipe, "test")

        monkeypatch.setattr("gateway.image_runner.run", fake_run)
        monkeypatch.setattr("gateway.image_recipes.auto_route", fake_auto_route)

        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable", plan_id=stored.plan_id, session_id=s.session_id
            )
        )
        assert captured["engine"] == "comfyui"
        assert captured["policy"] == {
            "content_lane": "safe",
            "consent_basis": None,
            "adult_confirmed": False,
        }


class TestDurableRoundTripDispatch:
    """B: plan → DB → require_approved_plan → dispatch keeps the policy."""

    @pytest.mark.asyncio
    async def test_private_plan_dispatch_carries_stored_policy(
        self, tmp_path: Path, monkeypatch
    ):
        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor, consent_basis="synthetic")

        plan = require_approved_plan(stored.plan_id, s.session_id)
        assert plan.content_lane == "private_adult"
        assert plan.consent_basis == "synthetic"
        assert plan.adult_confirmed is True

        captured: dict = {}
        _capture_run_edit(monkeypatch, captured)
        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable", plan_id=stored.plan_id, session_id=s.session_id
            )
        )
        run_edit_kwargs = captured["run_edit"]
        assert run_edit_kwargs["content_lane"] == "private_adult"
        assert run_edit_kwargs["consent_basis"] == "synthetic"
        assert run_edit_kwargs["adult_confirmed"] is True

    @pytest.mark.parametrize("basis", ["synthetic", "self"])
    def test_private_plan_round_trips_each_consent_basis(self, tmp_path: Path, basis: str):
        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor, consent_basis=basis)
        resumed = image_plans.require_plan(stored.plan_id)
        assert resumed.content_lane == "private_adult"
        assert resumed.consent_basis == basis
        assert resumed.adult_confirmed is True


class TestPrivateRequiresConsent:
    """C: private_adult with missing or invalid consent is refused pre-dispatch."""

    def test_seam_refuses_missing_consent(self):
        with pytest.raises(ConsentRequiredError):
            validate_image_execution_policy(
                "private_adult", None, True, "kitty_worker"
            )

    @pytest.mark.parametrize("bad_basis", ["", "third_party", "stable_diffusion", "gpt"])
    def test_seam_refuses_invalid_consent(self, bad_basis: str):
        with pytest.raises(ConsentRequiredError):
            validate_image_execution_policy(
                "private_adult", bad_basis, True, "kitty_worker"
            )

    def test_persist_refuses_missing_consent(self, tmp_path: Path):
        s, anchor = _private_session_with_anchor(tmp_path)
        with pytest.raises(PlanStoreError, match="consent_basis"):
            _persist_private_plan(s, anchor, consent_basis=None)

    def test_persist_refuses_invalid_consent(self, tmp_path: Path):
        s, anchor = _private_session_with_anchor(tmp_path)
        with pytest.raises(PlanStoreError, match="invalid consent_basis"):
            _persist_private_plan(s, anchor, consent_basis="third_party")


class TestPrivateRequiresAdult:
    """D: private_adult requires adult_confirmed=true."""

    def test_seam_refuses_missing_adult(self):
        with pytest.raises(AdultConfirmationRequiredError):
            validate_image_execution_policy(
                "private_adult", "synthetic", False, "kitty_worker"
            )

    @pytest.mark.parametrize("not_true", [0, 1.0, "True", "yes"])
    def test_seam_refuses_non_boolean_adult(self, not_true):
        """A truthy string is not an explicit boolean confirmation."""
        with pytest.raises(AdultConfirmationRequiredError):
            validate_image_execution_policy(
                "private_adult", "synthetic", not_true, "kitty_worker"
            )

    def test_persist_refuses_missing_adult(self, tmp_path: Path):
        s, anchor = _private_session_with_anchor(tmp_path)
        with pytest.raises(PlanStoreError, match="adult_confirmed"):
            _persist_private_plan(s, anchor, adult_confirmed=False)

    @pytest.mark.asyncio
    async def test_route_refuses_plan_without_adult(self, tmp_path: Path, monkeypatch):
        """Defence in depth: a stored row that deviates toward private_adult
        without an adult_confirmed flag must be refused at dispatch, even if it
        was written out-of-band (persist_plan itself already refuses)."""
        import gateway.paths as gp

        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor)
        with sqlite3.connect(gp.KITTY_DB_FILE) as conn:
            conn.execute(
                "UPDATE image_plans SET adult_confirmed = 0 WHERE plan_id = ?",
                (stored.plan_id,),
            )
            conn.commit()

        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=s.session_id
                )
            )
        assert exc.value.status_code == 400
        assert "adult" in str(exc.value.detail).lower()


class TestEligiblePrivateCombo:
    """E: private_adult+synthetic+true and private_adult+self+true are eligible;
    no third-party basis is accepted."""

    @pytest.mark.parametrize("basis", ["synthetic", "self"])
    def test_eligible_combos_pass_the_seam(self, basis: str):
        validate_image_execution_policy(basis and "private_adult", basis, True, "kitty_worker")

    @pytest.mark.parametrize("basis", [None, "", "third_party", "reproduced_anyone"])
    def test_non_canonical_bases_fail(self, basis):
        with pytest.raises(ImagePolicyError):
            validate_image_execution_policy("private_adult", basis, True, "kitty_worker")


class TestHostedLeakPrevention:
    """F: private_adult + any non-private target fails pre-dispatch; the hosted
    adapter never sees a call."""

    @pytest.mark.parametrize(
        "target",
        ["flux", "openrouter", "bfl", "runware", "google", "fal", "comfyui", "drawthings", "totally-unknown"],
    )
    def test_private_target_must_be_private(self, target: str):
        with pytest.raises(PrivateExecutionRequiredError):
            validate_image_execution_policy("private_adult", "synthetic", True, target)

    def test_safe_lane_ignores_target(self):
        validate_image_execution_policy("safe", None, False, "flux")
        validate_image_execution_policy(None, None, False, "comfyui")

    @pytest.mark.asyncio
    async def test_route_forces_private_executor_even_when_recipe_names_hosted(
        self, tmp_path: Path, monkeypatch
    ):
        """recipe metadata reporting a hosted provider must not steer a private
        plan: the private executor is chosen before estimate/availability."""
        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor)
        captured: dict = {}
        _capture_run_edit(monkeypatch, captured)
        # auto_route reports a hosted "flux" recipe; the plan must still run on
        # the private executor.
        monkeypatch.setattr(
            "gateway.image_recipes.auto_route",
            _edit_recipe_mock(captured, provider="flux"),
        )

        result = await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable", plan_id=stored.plan_id, session_id=s.session_id
            )
        )
        assert result["job_id"].startswith("job_")
        assert captured["run_edit"]["content_lane"] == "private_adult"


class TestFallbackLeakPrevention:
    """G: an unavailable private executor fails loud; nothing falls back or
    changes the lane on the way out."""

    @pytest.mark.asyncio
    async def test_route_refuses_when_private_executor_unavailable(
        self, tmp_path: Path, monkeypatch
    ):
        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor)

        from gateway.image_runner import ImageRunnerError

        async def fail_run_edit(*_args, **_kwargs):
            raise ImageRunnerError("private executor unavailable")

        async def fail_run(*_args, **_kwargs):
            raise AssertionError("no fallback from private to run()")

        monkeypatch.setattr("gateway.image_runner.run_edit", fail_run_edit)
        monkeypatch.setattr("gateway.image_runner.run", fail_run)
        monkeypatch.setattr(
            "gateway.image_recipes.auto_route", _edit_recipe_mock({})
        )

        with pytest.raises(HTTPException) as exc:
            await extended.studio_generate(
                extended.StudioGenerateRequest(
                    prompt="x", plan_id=stored.plan_id, session_id=s.session_id
                )
            )
        assert exc.value.status_code == 400


class TestPrivatePreflightTruth:
    """H: private work never invokes hosted availability or a spend reservation."""

    @pytest.mark.asyncio
    async def test_zero_hosted_preflight_for_private_plan(
        self, tmp_path: Path, monkeypatch
    ):
        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor)
        captured: dict = {}

        calls = {"paid_engine_available": 0, "reserve_attempt": 0}

        def counting_paid_engine_available(engine):
            calls["paid_engine_available"] += 1
            return True, ""

        def counting_reserve_attempt(*_args, **_kwargs):
            calls["reserve_attempt"] += 1

        monkeypatch.setattr(
            "gateway.image_runner.paid_engine_available", counting_paid_engine_available
        )
        monkeypatch.setattr(
            "gateway.image_sessions.reserve_attempt", counting_reserve_attempt
        )
        _capture_run_edit(monkeypatch, captured)

        result = await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable", plan_id=stored.plan_id, session_id=s.session_id
            )
        )
        assert result["job_id"].startswith("job_")
        assert calls["paid_engine_available"] == 0
        assert calls["reserve_attempt"] == 0


class TestRunnerBoundaryEnforcement:
    """I: the runner itself enforces the policy, so a direct run() cannot bypass
    the route."""

    @pytest.mark.parametrize("engine", ["flux", "openrouter"])
    @pytest.mark.asyncio
    async def test_direct_run_private_plus_hosted_refused(self, engine: str):
        from gateway.image_runner import run

        with pytest.raises(PrivateExecutionRequiredError):
            await run(
                engine,
                SENTINEL_PROMPT,
                content_lane="private_adult",
                consent_basis="synthetic",
                adult_confirmed=True,
            )

    @pytest.mark.asyncio
    async def test_direct_run_private_plus_unknown_refused(self):
        from gateway.image_runner import run

        with pytest.raises(PrivateExecutionRequiredError):
            await run(
                "comfyui",
                SENTINEL_PROMPT,
                content_lane="private_adult",
                consent_basis="self",
                adult_confirmed=True,
            )

    @pytest.mark.asyncio
    async def test_direct_run_edit_private_ok_when_worker_present(
        self, tmp_path: Path, monkeypatch
    ):
        """The private executor is run_edit(kitty_worker); a valid policy lands
        there and only there."""
        from gateway.image_runner import run_edit

        anchor = _succeeded_anchor(tmp_path)

        class StubWorker:
            async def upload_source_image(self, data, **_kw):
                from gateway.runpod_worker import WorkerImage

                return WorkerImage(
                    image_id=f"{'e' * 64}.png",
                    sha256="e" * 64,
                    media_type="image/png",
                    size_bytes=len(data),
                    width=1024,
                    height=1024,
                )

            async def submit(self, **kwargs):
                from gateway.runpod_worker import WorkerJob

                return WorkerJob(
                    job_id="w1",
                    status="queued",
                    workflow_sha256="f" * 64,
                    prompt_id=None,
                    submission_state="submitted",
                    error=None,
                    outputs=(),
                )

            async def wait(self, job_id, **_kw):
                from gateway.runpod_worker import WorkerJob, WorkerOutput

                return WorkerJob(
                    job_id=job_id,
                    status="succeeded",
                    workflow_sha256="f" * 64,
                    prompt_id="p1",
                    submission_state="submitted",
                    error=None,
                    outputs=(
                        WorkerOutput(
                            asset_id="asset_1",
                            filename="out.png",
                            media_type="image/png",
                            size_bytes=12,
                            sha256="a" * 64,
                            download_url="/v1/jobs/w1/outputs/asset_1",
                            width=1024,
                            height=1024,
                        ),
                    ),
                )

            async def download(self, output):
                return b"private-artifact-bytes"

        result = await run_edit(
            SENTINEL_PROMPT,
            anchor_job_id=anchor,
            worker=StubWorker(),
            content_lane="private_adult",
            consent_basis="self",
            adult_confirmed=True,
        )
        assert result.engine == "kitty_worker"


class TestRequestCannotOverride:
    """J: a mutable request cannot change the approved plan's policy."""

    @pytest.mark.asyncio
    async def test_safe_plan_stays_safe_despite_request_noise(self, monkeypatch):
        s = sessions.create_session()
        stored = persist_plan(s.session_id, _build_plan())
        captured: dict = {}

        async def fake_run(engine, prompt, **kwargs):
            captured["policy"] = {
                "content_lane": kwargs["content_lane"],
                "consent_basis": kwargs["consent_basis"],
                "adult_confirmed": kwargs["adult_confirmed"],
            }
            job = image_jobs.create_job(
                provider="comfyui", operation="txt2img", prompt=prompt
            )
            from gateway.image_runner import JobResult

            return JobResult(job_id=job.job_id, filename="/tmp/out.png", engine="comfyui")

        async def fail_run_edit(*_args, **_kwargs):
            raise AssertionError("a safe plan must not reach run_edit")

        def fake_auto_route(**kwargs):
            from gateway.image_recipes import Recipe, RoutingDecision

            recipe = Recipe(
                recipe_id="r_default",
                display_name="Default",
                description=None,
                provider="comfyui",
                workflow_template_id=None,
                model_family=None,
            )
            return RoutingDecision(recipe.recipe_id, recipe, "test")

        monkeypatch.setattr("gateway.image_runner.run", fake_run)
        monkeypatch.setattr("gateway.image_runner.run_edit", fail_run_edit)
        monkeypatch.setattr("gateway.image_recipes.auto_route", fake_auto_route)

        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable",
                plan_id=stored.plan_id,
                session_id=s.session_id,
                # Pydantic ignores unknown keys: a mutated client payload must
                # have no effect on the stored policy.
                content_lane="private_adult",
                consent_basis="synthetic",
                adult_confirmed=True,
            )
        )
        assert captured["policy"] == {
            "content_lane": "safe",
            "consent_basis": None,
            "adult_confirmed": False,
        }

    @pytest.mark.asyncio
    async def test_private_plan_stays_private(self, tmp_path: Path, monkeypatch):
        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor, consent_basis="self")
        captured: dict = {}
        _capture_run_edit(monkeypatch, captured)

        await extended.studio_generate(
            extended.StudioGenerateRequest(
                prompt="mutable",
                plan_id=stored.plan_id,
                session_id=s.session_id,
                content_lane="safe",
                consent_basis=None,
                adult_confirmed=False,
            )
        )
        assert captured["run_edit"]["content_lane"] == "private_adult"
        assert captured["run_edit"]["consent_basis"] == "self"
        assert captured["run_edit"]["adult_confirmed"] is True


class TestKeywordsHaveZeroAuthority:
    """K: EXPLICIT_KW in a prompt grants nothing; trusted plan metadata is the
    only way into the private lane."""

    def test_prompt_keywords_do_not_enter_the_private_lane(self):
        plan = _build_plan()
        assert plan.content_lane == "safe"
        assert plan.consent_basis is None
        assert plan.adult_confirmed is False

        from gateway.image_gen import EXPLICIT_KW, _parse

        explicit_sentinel = "a study of an erect cock, explicit, in studio light"
        lowered = explicit_sentinel.lower()
        assert any(k in lowered for k in EXPLICIT_KW)
        parsed = _parse(explicit_sentinel)
        assert parsed["explicit"] is True
        # The parse output is workflow conditioning, never an authorization
        # signal — the plan still declares safe even for a keyword-loaded prompt.
        plan = _build_plan()
        assert plan.content_lane == "safe"

    def test_explicit_keyword_prompt_does_not_persist_private(self):
        s = sessions.create_session()
        plan = build_image_plan(SENTINEL_PROMPT)
        stored = persist_plan(s.session_id, plan)
        assert stored.content_lane == "safe"
        assert stored.consent_basis is None
        assert stored.adult_confirmed is False

    def test_neutral_prompt_plus_trusted_metadata_enters_private_lane(
        self, tmp_path: Path
    ):
        """No keyword in SENTINEL_PROMPT; only trusted plan metadata declares
        the private lane."""
        s, anchor = _private_session_with_anchor(tmp_path)
        stored = _persist_private_plan(s, anchor)
        assert stored.content_lane == "private_adult"
        assert stored.consent_basis == "synthetic"
        assert stored.adult_confirmed is True

    @pytest.mark.asyncio
    async def test_plan_endpoint_accepts_policy_declaration(self, tmp_path: Path):
        s, anchor = _private_session_with_anchor(tmp_path)
        result = await extended.studio_plan(
            extended.PlanPreviewRequest(
                prompt=SENTINEL_PROMPT,
                session_id=s.session_id,
                content_lane="private_adult",
                consent_basis="synthetic",
                adult_confirmed=True,
            )
        )
        resumed = image_plans.require_plan(result["plan_id"])
        assert resumed.content_lane == "private_adult"
        assert resumed.consent_basis == "synthetic"
        assert resumed.adult_confirmed is True
