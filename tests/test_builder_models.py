"""Tests for gateway/models/builder.py, builder_runner context injection,
and companion wiring (agent presets).

Phase 2 upgrade: Pydantic models, context injection, and agent preset dispatch.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from pydantic import ValidationError

from gateway.models.builder import (
    AgentDispatchRequest,
    AgentDispatchResult,
    AgentPreset,
    AgentPresetConfig,
    AttemptResult,
    Assumption,
    ContextTier,
    EvidenceCriterion,
    Mission,
    MissionAuthority,
    MissionBudgets,
    MissionContext,
    MissionEvidencePlan,
    MissionExecution,
    MissionOrigin,
    MissionState,
    ReviewContract,
    RiskTier,
    WorkerContextBundle,
    WorkerContract,
)


# ===========================================================================
# Model tests
# ===========================================================================


class TestMissionModel:
    def test_mission_defaults(self):
        m = Mission(mission_id="kb_mission_001", objective="Do the thing")
        assert m.mission_id == "kb_mission_001"
        assert m.objective == "Do the thing"
        assert m.schema_version == 1
        assert m.state == MissionState.proposed
        assert m.budgets.max_attempts == 3
        assert m.authority.risk_tier == RiskTier.t2

    def test_mission_serialization(self):
        m = Mission(
            mission_id="kb_mission_002",
            objective="Test serialization",
            rationale="Because we need to test",
            non_goals=["Skip this", "Skip that"],
            authority=MissionAuthority(risk_tier=RiskTier.t0),
            budgets=MissionBudgets(max_attempts=5, max_time_seconds=7200),
        )
        data = m.model_dump()
        assert data["mission_id"] == "kb_mission_002"
        assert data["objective"] == "Test serialization"
        assert data["rationale"] == "Because we need to test"
        assert data["non_goals"] == ["Skip this", "Skip that"]
        assert data["authority"]["risk_tier"] == "t0"
        assert data["budgets"]["max_attempts"] == 5

    def test_mission_deserialization(self):
        data = {
            "mission_id": "kb_mission_003",
            "objective": "Round-trip test",
            "state": "approved",
            "authority": {"risk_tier": "t1"},
            "budgets": {"max_attempts": 10},
        }
        m = Mission(**data)
        assert m.mission_id == "kb_mission_003"
        assert m.state == MissionState.approved
        assert m.authority.risk_tier == RiskTier.t1
        assert m.budgets.max_attempts == 10

    def test_mission_rejects_empty_mission_id(self):
        with pytest.raises(ValidationError):
            Mission(mission_id="", objective="test")

    def test_mission_minimal_valid(self):
        m = Mission(mission_id="kb_001", objective="test")
        assert m.mission_id == "kb_001"

    def test_mission_origin_defaults(self):
        o = MissionOrigin()
        assert o.conversation_id is None
        assert o.message_refs == []
        assert o.repository is None

    def test_mission_origin_with_values(self):
        o = MissionOrigin(
            conversation_id="conv_123",
            message_refs=["ref1", "ref2"],
            repository="owner/repo",
            base_sha="abc123def456",
        )
        assert o.conversation_id == "conv_123"
        assert len(o.message_refs) == 2
        assert o.base_sha == "abc123def456"

    def test_assumption_model(self):
        a = Assumption(claim="The sky is blue", evidence="Observed", disposition="confirmed")
        assert a.claim == "The sky is blue"
        assert a.evidence == "Observed"
        assert a.disposition == "confirmed"

    def test_mission_context_with_assumptions(self):
        ctx = MissionContext(
            required_refs=["ref_a"],
            missing=["config file"],
            assumptions=[
                Assumption(claim="DB is available"),
            ],
        )
        assert len(ctx.assumptions) == 1
        assert ctx.assumptions[0].claim == "DB is available"

    def test_mission_execution(self):
        ex = MissionExecution(
            strategy="parallel",
            packets=["p1", "p2"],
            allowed_paths=["gateway/"],
            forbidden_operations=["push", "merge"],
        )
        assert ex.strategy == "parallel"
        assert "gateway/" in ex.allowed_paths

    def test_mission_evidence_plan(self):
        ep = MissionEvidencePlan(
            acceptance_criteria=[EvidenceCriterion(description="tests pass")],
            validation_commands=["pytest tests/"],
            independent_review=True,
        )
        assert len(ep.acceptance_criteria) == 1
        assert ep.acceptance_criteria[0].description == "tests pass"
        assert ep.independent_review is True

    def test_mission_expiry(self):
        future = datetime.now() + timedelta(hours=1)
        auth = MissionAuthority(expires_at=future)
        assert auth.expires_at is not None
        assert auth.expires_at > datetime.now()


class TestMissionState:
    def test_states_have_correct_values(self):
        assert MissionState.proposed.value == "proposed"
        assert MissionState.approved.value == "approved"
        assert MissionState.succeeded.value == "succeeded"
        assert MissionState.failed.value == "failed"
        assert MissionState.cancelled.value == "cancelled"
        assert MissionState.superseded.value == "superseded"

    def test_all_states_are_unique(self):
        values = [s.value for s in MissionState]
        assert len(values) == len(set(values))


class TestAgentPreset:
    def test_presets_have_correct_values(self):
        assert AgentPreset.explorer.value == "explorer"
        assert AgentPreset.planner.value == "planner"
        assert AgentPreset.coder.value == "coder"
        assert AgentPreset.reviewer.value == "reviewer"
        assert AgentPreset.researcher.value == "researcher"

    def test_all_presets_are_unique(self):
        values = [p.value for p in AgentPreset]
        assert len(values) == len(set(values))


class TestRiskTier:
    def test_tiers_have_correct_values(self):
        assert RiskTier.t0.value == "t0"
        assert RiskTier.t1.value == "t1"
        assert RiskTier.t2.value == "t2"


class TestContextTier:
    def test_tiers_have_correct_values(self):
        assert ContextTier.trivial.value == "trivial"
        assert ContextTier.standard.value == "standard"
        assert ContextTier.deep.value == "deep"


# ===========================================================================
# Worker context/contract model tests
# ===========================================================================


class TestWorkerContextBundle:
    def test_defaults(self):
        ctx = WorkerContextBundle(task_id="kb_t1", run_id="run_abc", branch="feat/test")
        assert ctx.task_id == "kb_t1"
        assert ctx.run_id == "run_abc"
        assert ctx.branch == "feat/test"
        assert ctx.allowed_paths == []
        assert ctx.acceptance_criteria == []
        assert ctx.agent_preset is None

    def test_with_preset(self):
        ctx = WorkerContextBundle(
            task_id="kb_t2",
            run_id="run_def",
            branch="feat/test",
            agent_preset=AgentPreset.coder,
        )
        assert ctx.agent_preset == AgentPreset.coder

    def test_with_all_fields(self):
        ctx = WorkerContextBundle(
            task_id="kb_t3",
            run_id="run_ghi",
            branch="feat/test",
            brief_path="/tmp/brief.md",
            bundle_path="/tmp/bundle.json",
            result_path="/tmp/result.json",
            context_manifest_path="/tmp/manifest.json",
            attempt_id="1",
            agent_preset=AgentPreset.explorer,
            model="gpt-4",
            provider="openai",
            tier=ContextTier.deep,
            allowed_paths=["gateway/"],
            acceptance_criteria=["tests pass"],
        )
        assert ctx.model == "gpt-4"
        assert ctx.tier == ContextTier.deep


class TestWorkerContract:
    def test_defaults(self):
        c = WorkerContract(status="completed")
        assert c.status == "completed"
        assert c.changed_paths == []
        assert c.errors == []

    def test_with_data(self):
        c = WorkerContract(
            status="completed",
            summary="Implemented feature X",
            changed_paths=["gateway/foo.py", "gateway/bar.py"],
            validation_results=[{"command": "pytest", "passed": True}],
        )
        assert len(c.changed_paths) == 2
        assert len(c.validation_results) == 1

    def test_no_status(self):
        with pytest.raises(ValidationError):
            WorkerContract()


class TestReviewContract:
    def test_defaults(self):
        rc = ReviewContract(verdict="approve")
        assert rc.verdict == "approve"
        assert rc.findings == []

    def test_with_findings(self):
        rc = ReviewContract(
            verdict="reject",
            summary="Has critical issues",
            findings=[
                {"severity": "critical", "note": "Security hole"},
                {"severity": "minor", "note": "Typo"},
            ],
        )
        assert len(rc.findings) == 2
        assert rc.findings[0]["severity"] == "critical"


class TestAttemptResult:
    def test_defaults(self):
        ar = AttemptResult(attempt_id=1, attempt_no=1, outcome="succeeded")
        assert ar.attempt_id == 1
        assert ar.outcome == "succeeded"
        assert ar.changed_paths == []

    def test_with_failure(self):
        ar = AttemptResult(
            attempt_id=2, attempt_no=1, outcome="failed",
            failure="Validation failed",
            scope_violations=["outside.txt"],
        )
        assert ar.failure == "Validation failed"
        assert "outside.txt" in ar.scope_violations


# ===========================================================================
# Agent dispatch model tests
# ===========================================================================


class TestAgentDispatchRequest:
    def test_minimal(self):
        req = AgentDispatchRequest(goal="Test something", preset=AgentPreset.coder)
        assert req.goal == "Test something"
        assert req.preset == AgentPreset.coder

    def test_with_extra(self):
        req = AgentDispatchRequest(
            goal="Research topic",
            preset="researcher",
            task_id="kb_t1",
            extra_context="Here is background",
            model="claude-3",
        )
        assert req.preset == "researcher"
        assert req.extra_context == "Here is background"


class TestAgentDispatchResult:
    def test_success(self):
        result = AgentDispatchResult(
            session_id=42,
            preset="coder",
            goal="Implement feature",
            status="completed",
            output="Done",
        )
        assert result.session_id == 42
        assert result.status == "completed"

    def test_failure(self):
        result = AgentDispatchResult(
            session_id=0,
            preset="coder",
            goal="Do thing",
            status="failed",
            error="Something broke",
        )
        assert result.error == "Something broke"


class TestAgentPresetConfig:
    def test_valid_config(self):
        cfg = AgentPresetConfig(
            preset=AgentPreset.coder,
            description="Write code",
            system_prompt="You are a coder",
            max_iterations=5,
            temperature=0.2,
            timeout_seconds=600,
        )
        assert cfg.preset == AgentPreset.coder
        assert cfg.max_iterations == 5
        assert cfg.timeout_seconds == 600

    def test_default_values(self):
        cfg = AgentPresetConfig(
            preset=AgentPreset.explorer,
            description="Explore",
            system_prompt="You are an explorer",
        )
        assert cfg.max_iterations == 3
        assert cfg.temperature == 0.3
        assert cfg.timeout_seconds == 300
        assert cfg.tier == ContextTier.standard


# ===========================================================================
# Context injection tests
# ===========================================================================


class TestInjectWorkerContext:
    def test_inject_creates_files(self, tmp_path: Path):
        from gateway.builder_runner import inject_worker_context

        db_path = tmp_path / "queue" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        bq.init_db(db_path)
        task = bq.create_task("test context injection", db_path=db_path)

        claimed = bq.claim_task(task["id"], "test-worker", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        extra_env, ctx_bundle = inject_worker_context(
            task["id"],
            run["id"],
            branch="feat/test",
            worker="test-worker",
            allowed_paths=["gateway/"],
            acceptance_criteria=["tests pass"],
            db_path=db_path,
        )

        assert "KB_CONTEXT_BUNDLE_PATH" in extra_env
        assert "KB_CONTEXT_MANIFEST_PATH" in extra_env

        bundle_path = Path(extra_env["KB_CONTEXT_BUNDLE_PATH"])
        manifest_path = Path(extra_env["KB_CONTEXT_MANIFEST_PATH"])
        assert bundle_path.exists()
        assert manifest_path.exists()

        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        assert bundle["task_id"] == task["id"]
        assert bundle["run_id"] == run["id"]
        assert bundle["allowed_paths"] == ["gateway/"]
        assert bundle["acceptance_criteria"] == ["tests pass"]

    def test_inject_context_bundle_fields(self, tmp_path: Path):
        from gateway.builder_runner import inject_worker_context

        db_path = tmp_path / "queue2" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        bq.init_db(db_path)
        task = bq.create_task("test fields", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )

        extra_env, ctx_bundle = inject_worker_context(
            task["id"],
            run["id"],
            branch="feat/fields",
            worker="w",
            model="gpt-4",
            provider="openai",
            agent_preset="coder",
            db_path=db_path,
        )

        assert ctx_bundle.task_id == task["id"]
        assert ctx_bundle.run_id == run["id"]
        assert ctx_bundle.branch == "feat/fields"
        assert ctx_bundle.model == "gpt-4"
        assert ctx_bundle.provider == "openai"
        assert ctx_bundle.agent_preset == AgentPreset.coder
        assert ctx_bundle.bundle_path == extra_env["KB_CONTEXT_BUNDLE_PATH"]

    def test_inject_context_no_events_graceful(self, tmp_path: Path):
        from gateway.builder_runner import inject_worker_context

        db_path = tmp_path / "queue3" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        bq.init_db(db_path)
        task = bq.create_task("test no events", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )

        extra_env, ctx_bundle = inject_worker_context(
            task["id"],
            run["id"],
            branch="feat/no-events",
            db_path=db_path,
        )

        assert "KB_CONTEXT_BUNDLE_PATH" in extra_env


class TestValidateWorkerContext:
    def test_validate_valid_context(self, tmp_path: Path):
        from gateway.builder_runner import inject_worker_context, validate_worker_context

        db_path = tmp_path / "queue4" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        bq.init_db(db_path)
        task = bq.create_task("test validate", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        inject_worker_context(task["id"], run["id"], branch="feat/valid", db_path=db_path)

        issues = validate_worker_context(task["id"], run["id"], db_path=db_path)
        assert issues == []

    def test_validate_missing_bundle(self, tmp_path: Path):
        from gateway.builder_runner import validate_worker_context

        db_path = tmp_path / "queue5" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        bq.init_db(db_path)
        task = bq.create_task("test missing bundle", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )

        issues = validate_worker_context(task["id"], run["id"], db_path=db_path)
        assert any("context bundle missing" in i for i in issues)

    def test_validate_corrupted_bundle(self, tmp_path: Path):
        from gateway.builder_runner import inject_worker_context, validate_worker_context

        db_path = tmp_path / "queue6" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        from gateway.paths import BUILDER_QUEUE_DB
        bq.init_db(db_path)
        task = bq.create_task("test corrupt", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        inject_worker_context(task["id"], run["id"], branch="feat/corrupt", db_path=db_path)

        run_dir = db_path.parent / "runs" / run["id"]
        bundle_path = run_dir / "context-bundle.json"
        bundle_path.write_text("not json", encoding="utf-8")

        issues = validate_worker_context(task["id"], run["id"], db_path=db_path)
        assert any("unreadable" in i for i in issues)

    def test_validate_task_id_mismatch(self, tmp_path: Path):
        from gateway.builder_runner import inject_worker_context, validate_worker_context

        db_path = tmp_path / "queue7" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        bq.init_db(db_path)
        task = bq.create_task("test mismatch", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )
        inject_worker_context(task["id"], run["id"], branch="feat/mismatch", db_path=db_path)

        run_dir = db_path.parent / "runs" / run["id"]
        bundle_path = run_dir / "context-bundle.json"
        bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        bundle["task_id"] = "wrong-task-id"
        bundle_path.write_text(json.dumps(bundle), encoding="utf-8")

        issues = validate_worker_context(task["id"], run["id"], db_path=db_path)
        assert any("mismatch" in i for i in issues)


# ===========================================================================
# Companion wiring tests
# ===========================================================================


class TestAgentPresetConfigs:
    def test_all_presets_have_configs(self):
        from gateway.builder_runner import AGENT_PRESET_CONFIGS

        for preset in AgentPreset:
            assert preset in AGENT_PRESET_CONFIGS, f"Missing config for {preset}"

    def test_each_config_has_valid_structure(self):
        from gateway.builder_runner import AGENT_PRESET_CONFIGS

        for preset, config in AGENT_PRESET_CONFIGS.items():
            assert config.preset == preset
            assert config.description, f"Empty description for {preset}"
            assert config.system_prompt, f"Empty system_prompt for {preset}"
            assert config.max_iterations >= 1
            assert 0 < config.temperature <= 1
            assert config.timeout_seconds >= 30

    def test_explorer_config(self):
        from gateway.builder_runner import AGENT_PRESET_CONFIGS

        cfg = AGENT_PRESET_CONFIGS[AgentPreset.explorer]
        assert cfg.max_iterations == 3
        assert cfg.temperature == 0.5
        assert cfg.timeout_seconds == 300

    def test_coder_config(self):
        from gateway.builder_runner import AGENT_PRESET_CONFIGS

        cfg = AGENT_PRESET_CONFIGS[AgentPreset.coder]
        assert cfg.max_iterations == 5
        assert cfg.temperature == 0.2
        assert cfg.timeout_seconds == 600

    def test_researcher_config(self):
        from gateway.builder_runner import AGENT_PRESET_CONFIGS

        cfg = AGENT_PRESET_CONFIGS[AgentPreset.researcher]
        assert cfg.max_iterations == 4
        assert cfg.timeout_seconds == 600


class TestRunAgentPreset:
    def test_unknown_preset_returns_error(self):
        from gateway.builder_runner import run_agent_preset
        import asyncio

        result = asyncio.run(run_agent_preset("test goal", "nonexistent"))
        assert result["status"] == "failed"
        assert "Unknown agent preset" in result["error"]


# ===========================================================================
# Runner integration tests (context injection wiring)
# ===========================================================================


class TestRunWorkerContextInjection:
    def test_run_worker_creates_context_files_when_enabled(self, repo: Path, db_path: Path):
        from gateway import builder_runner as br

        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo task=$KB_TASK_ID bundle=${KB_CONTEXT_BUNDLE_PATH:-unset}"],
            worker="test-worker",
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
            inject_context=True,
        )

        assert run["final_report"]["context_injected"] is True
        log = Path(run["log_path"]).read_text()
        assert f"task={task['id']}" in log

    def test_run_worker_skips_context_when_disabled(self, repo: Path, db_path: Path):
        from gateway import builder_runner as br

        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            ["sh", "-c", "echo bundle=${KB_CONTEXT_BUNDLE_PATH:-unset}"],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
            inject_context=False,
        )

        assert run["final_report"]["context_injected"] is False
        log = Path(run["log_path"]).read_text()
        assert "bundle=unset" in log

    def test_worker_receives_context_env_vars(self, repo: Path, db_path: Path):
        from gateway import builder_runner as br

        task = _queued_task(db_path)
        run = br.run_worker(
            task["id"],
            [
                "sh", "-c",
                "echo bundle=${KB_CONTEXT_BUNDLE_PATH:-unset} "
                "manifest=${KB_CONTEXT_MANIFEST_PATH:-unset}",
            ],
            timeout_seconds=30,
            heartbeat_seconds=1,
            repo_root=repo,
            db_path=db_path,
            inject_context=True,
        )

        log = Path(run["log_path"]).read_text()
        assert "bundle=unset" not in log
        assert "manifest=unset" not in log
        assert "bundle=" in log
        assert "manifest=" in log

    def test_report_includes_context_issues_when_validation_fails(
        self, repo: Path, db_path: Path, monkeypatch
    ):
        from gateway import builder_runner as br

        task = _queued_task(db_path)

        def always_fail(*args, **kwargs):
            return ["context bundle missing: /nonexistent"]

        monkeypatch.setattr(br, "validate_worker_context", always_fail)

        with pytest.raises(br.RunnerError, match="context validation failed"):
            br.run_worker(
                task["id"],
                ["sh", "-c", "echo ok"],
                timeout_seconds=10,
                heartbeat_seconds=1,
                repo_root=repo,
                db_path=db_path,
                inject_context=True,
            )

    def test_inject_context_repo_root(self, tmp_path: Path):
        """inject_worker_context handles repo_root for context manifest."""
        from gateway import builder_runner as br

        db_path = tmp_path / "queue8" / "builder_queue.db"
        db_path.parent.mkdir(parents=True)
        from gateway import builder_queue as bq
        bq.init_db(db_path)
        task = bq.create_task("test repo root", db_path=db_path)
        claimed = bq.claim_task(task["id"], "w", db_path=db_path)
        run = bq.create_run(
            task["id"], ["true"],
            lease_token=claimed["lease_token"],
            claim_version=claimed["claim_version"],
            db_path=db_path,
        )

        extra_env, ctx_bundle = br.inject_worker_context(
            task["id"],
            run["id"],
            branch="feat/repo-root",
            worker="w",
            repo_root=tmp_path,
            db_path=db_path,
        )
        assert "KB_CONTEXT_BUNDLE_PATH" in extra_env
        assert "KB_CONTEXT_MANIFEST_PATH" in extra_env


# ===========================================================================
# Helpers (mirrored from test_builder_runner.py to avoid cross-module dep)
# ===========================================================================


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    import subprocess
    root = tmp_path / "repo"
    root.mkdir()
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.email", "t@t"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "t"], cwd=root, check=True)
    (root / "README.md").write_text("hello\n")
    subprocess.run(["git", "add", "."], cwd=root, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "init"], cwd=root, check=True)
    return root


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    from gateway import builder_queue as bq
    p = tmp_path / "queue" / "builder_queue.db"
    bq.init_db(p)
    return p


def _queued_task(db_path: Path, **kwargs) -> dict:
    from gateway import builder_queue as bq
    return bq.create_task("runner test task", db_path=db_path, **kwargs)