from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import discord
import pytest

from integrations.discord_command_center.adapters.codex import CodexAdapter
from integrations.discord_command_center.bot import VibeController, split_discord_message
from integrations.discord_command_center.config import CommandCenterConfig
from integrations.discord_command_center.models import ProgressEvent
from integrations.discord_command_center.runner import (
    build_child_environment,
    build_sandbox_profile,
)
from integrations.discord_command_center.service import VibeService
from integrations.discord_command_center.workspace import GitWorktreeManager

PYTHON = "/Users/jacobbrizinski/Projects/kitty/venv/bin/python"


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(
        ["/usr/bin/git", "-C", str(repo), *args],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _init_repo(path: Path) -> None:
    path.mkdir()
    _git(path, "init")
    _git(path, "config", "user.email", "phase0@example.invalid")
    _git(path, "config", "user.name", "Phase Zero")
    (path / "README.md").write_text("phase zero\n")
    _git(path, "add", "README.md")
    _git(path, "commit", "-m", "init")


def test_codex_command_is_bounded_readonly_argv(tmp_path: Path) -> None:
    adapter = CodexAdapter(executable="/bin/echo", model="test-model")

    command = adapter.command("inspect only", tmp_path)

    assert command[0] == "/bin/echo"
    exec_index = command.index("exec")
    assert command[exec_index + 1 : exec_index + 3] == ("--ignore-user-config", "--ephemeral")
    for feature in ("apps", "plugins", "browser_use", "computer_use", "image_generation", "multi_agent"):
        assert ("--disable", feature) == command[command.index(feature) - 1 : command.index(feature) + 1]
    assert ("--cd", str(tmp_path)) == command[command.index("--cd") : command.index("--cd") + 2]
    assert "--ignore-user-config" in command
    assert ("--sandbox", "danger-full-access") == command[
        command.index("--sandbox") : command.index("--sandbox") + 2
    ]
    assert "--json" in command
    assert ("--model", "test-model") == command[
        command.index("--model") : command.index("--model") + 2
    ]
    assert command[-1].endswith("inspect only")


def test_child_environment_is_allowlisted_and_secret_free(monkeypatch) -> None:
    source = {
        "HOME": "/Users/test",
        "PATH": "/opt/homebrew/bin:/Users/test/bin:/usr/local/bin",
        "LANG": "en_CA.UTF-8",
        "TERM": "xterm-256color",
        "CODEX_HOME": "/Users/test/.codex",
        "OPENAI_API_KEY": "sk-secret",
        "DISCORD_BOT_TOKEN": "discord-secret",
        "COMMAND_CENTER_DISCORD_TOKEN": "another-secret",
    }

    child = build_child_environment(source)

    assert child["HOME"] == "/Users/test"
    assert child["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"
    assert child["CODEX_HOME"] == "/Users/test/.codex"
    assert "OPENAI_API_KEY" not in child
    assert "DISCORD_BOT_TOKEN" not in child
    assert "COMMAND_CENTER_DISCORD_TOKEN" not in child


def test_discord_config_requires_an_authorization_allowlist() -> None:
    config = CommandCenterConfig(
        repo=Path("/tmp/repo"),
        discord_token="token",
        guild_id=1,
    )

    with pytest.raises(RuntimeError, match="authorization"):
        config.require_discord()


def test_worktree_audit_detects_untracked_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitWorktreeManager(repo=repo, base_ref="HEAD")

    worktree = manager.create("audit-run")
    assert manager.audit(worktree).files == 0

    (worktree / "unexpected.txt").write_text("mutation\n")
    audit = manager.audit(worktree)

    assert audit.files == 1
    assert audit.dirty is True
    assert "unexpected.txt" in audit.status_lines[0]


def test_worktree_audit_detects_ignored_mutation(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    (repo / ".gitignore").write_text("ignored.txt\n")
    _git(repo, "add", ".gitignore")
    _git(repo, "commit", "-m", "ignore fixture")
    manager = GitWorktreeManager(repo=repo, base_ref="HEAD")

    worktree = manager.create("ignored-audit-run")
    (worktree / "ignored.txt").write_text("hidden mutation\n")

    audit = manager.audit(worktree)

    assert audit.dirty is True
    assert any("ignored.txt" in line for line in audit.status_lines)


def test_worktree_audit_uses_authenticated_git_metadata_after_git_file_tamper(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitWorktreeManager(repo=repo, base_ref="HEAD")
    worktree = manager.create("authenticated-audit-run")

    (worktree / ".git").write_text("gitdir: /tmp/attacker-gitdir\n")
    (worktree / "unexpected.txt").write_text("mutation\n")

    audit = manager.audit(worktree)

    assert audit.dirty is True
    assert any("unexpected.txt" in line for line in audit.status_lines)


def test_worktree_creation_cleans_exact_path_after_authentication_failure(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitWorktreeManager(repo=repo, run_root=tmp_path / "runs")
    unrelated = manager.create("unrelated-run")
    failed_path = manager.run_root / "failed-auth-run"
    original_git_path = manager._git_path

    def fail_for_new_worktree(*args: str, cwd: Path) -> Path:
        if cwd.resolve() == failed_path.resolve():
            raise RuntimeError("simulated identity validation failure")
        return original_git_path(*args, cwd=cwd)

    monkeypatch.setattr(manager, "_git_path", fail_for_new_worktree)

    with pytest.raises(RuntimeError, match="simulated identity"):
        manager.create("failed-auth-run")

    assert not failed_path.exists()
    assert unrelated.exists()
    assert str(failed_path) not in _git(repo, "worktree", "list", "--porcelain")


def test_worktree_creation_preserves_authentication_failure_when_cleanup_is_unconfirmed(
    tmp_path: Path, monkeypatch
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitWorktreeManager(repo=repo, run_root=tmp_path / "runs")
    unrelated = manager.create("unrelated-run")
    failed_path = manager.run_root / "failed-auth-run"
    original_git_path = manager._git_path
    original_git = manager._git

    def fail_authentication(*args: str, cwd: Path) -> Path:
        if cwd.resolve() == failed_path.resolve():
            raise RuntimeError("authentication failed")
        return original_git_path(*args, cwd=cwd)

    def fail_exact_cleanup(*args: str, cwd: Path) -> str:
        if args[:3] == ("worktree", "remove", "--force") and Path(args[3]).resolve() == failed_path.resolve():
            raise RuntimeError("cleanup remove failed")
        return original_git(*args, cwd=cwd)

    monkeypatch.setattr(manager, "_git_path", fail_authentication)
    monkeypatch.setattr(manager, "_git", fail_exact_cleanup)

    with pytest.raises(RuntimeError, match="authentication failed") as raised:
        manager.create("failed-auth-run")

    assert raised.value.__cause__ is not None
    assert "cleanup not confirmed" in str(raised.value)
    assert unrelated.exists()
    assert failed_path.exists()
    assert str(failed_path) in _git(repo, "worktree", "list", "--porcelain")


def test_service_reports_terminal_cleanup_failure_as_failed_event(tmp_path: Path) -> None:
    service, manager = _make_service(tmp_path, mutate=False)

    def fail_remove(path: Path) -> None:
        raise RuntimeError("cleanup remove failed")

    manager.remove = fail_remove  # type: ignore[method-assign]

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "failed"
    assert events[-1].code == "worktree_cleanup_failed"
    assert "cleanup remove failed" in events[-1].message


def test_worktree_audit_stays_bound_to_captured_base_commit_when_ref_moves(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    _git(repo, "branch", "audit-base")
    manager = GitWorktreeManager(repo=repo, base_ref="audit-base", run_root=tmp_path / "runs")
    worktree = manager.create("moving-base-ref")

    _git(repo, "commit", "--allow-empty", "-m", "advance canonical HEAD")
    _git(repo, "branch", "-f", "audit-base", "HEAD")

    assert manager.audit(worktree).files == 0


class _FakeRunner:
    def __init__(self, *, mutate: bool = False) -> None:
        self.mutate = mutate
        self.calls: list[tuple[tuple[str, ...], Path, dict[str, str], int]] = []

    async def stream(self, command, *, cwd, environment, timeout_seconds):
        self.calls.append((command, cwd, environment, timeout_seconds))
        if self.mutate:
            (cwd / "readonly-violation.txt").write_text("bad\n")
        yield ProgressEvent(kind="progress", message="codex started")
        yield ProgressEvent(kind="process_exit", message="codex exited", exit_code=0)


def _make_service(tmp_path: Path, *, mutate: bool) -> tuple[VibeService, GitWorktreeManager]:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitWorktreeManager(
        repo=repo,
        base_ref="HEAD",
        run_root=tmp_path / "runs",
    )
    codex_home = tmp_path / "codex-home"
    codex_home.mkdir()
    (codex_home / "auth.json").write_text("{}")
    service = VibeService(
        workspace=manager,
        adapter=CodexAdapter(executable="/bin/echo", model="test-model"),
        runner=_FakeRunner(mutate=mutate),
        timeout_seconds=9,
        environment={
            "HOME": str(tmp_path),
            "PATH": "/usr/bin:/bin",
            "CODEX_HOME": str(codex_home),
        },
    )
    return service, manager


def test_clean_readonly_run_removes_disposable_worktree(tmp_path: Path) -> None:
    service, manager = _make_service(tmp_path, mutate=False)

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "done"
    assert events[-1].code is None
    assert list(manager.run_root.glob("*")) == []


def test_readonly_violation_fails_loud_and_preserves_worktree(tmp_path: Path) -> None:
    service, manager = _make_service(tmp_path, mutate=True)

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "failed"
    assert events[-1].code == "readonly_violation"
    preserved = list(manager.run_root.glob("*"))
    assert len(preserved) == 1
    assert (preserved[0] / "readonly-violation.txt").exists()


async def _collect(stream) -> list[ProgressEvent]:
    return [event async for event in stream]


def test_discord_message_splitter_never_exceeds_1900_chars() -> None:
    text = "x" * 5000
    chunks = split_discord_message(text)

    assert "".join(chunks) == text
    assert max(map(len, chunks)) <= 1900


class _Response:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    async def defer(self, *, ephemeral: bool = False, thinking: bool = False) -> None:
        self.log.append("defer")


class _SentMessage:
    def __init__(self, thread: "_Thread", index: int) -> None:
        self.thread = thread
        self.index = index

    async def edit(self, *, content: str) -> None:
        self.thread.log.append("message_edit")
        self.thread.edit_history.append(content)
        self.thread.messages[self.index] = content


class _Thread:
    mention = "<#thread>"

    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.messages: list[str] = []
        self.edit_history: list[str] = []

    async def add_user(self, user) -> None:
        self.log.append("add_user")

    async def send(self, content: str) -> _SentMessage:
        self.log.append("thread_send")
        self.messages.append(content)
        return _SentMessage(self, len(self.messages) - 1)


class _Channel:
    def __init__(self, log: list[str], thread: _Thread) -> None:
        self.log = log
        self.thread = thread
        self.created_kwargs: dict[str, object] = {}

    async def create_thread(self, **kwargs):
        self.log.append("create_thread")
        self.created_kwargs = kwargs
        return self.thread


class _Followup:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.messages: list[str] = []

    async def send(self, content: str, *, ephemeral: bool = False) -> None:
        self.log.append("followup")
        self.messages.append(content)


class _Interaction:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.response = _Response(log)
        self.thread = _Thread(log)
        self.channel = _Channel(log, self.thread)
        self.followup = _Followup(log)
        self.user = object()


class _FakeService:
    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.requests: list[str] = []

    async def run(self, request: str):
        self.requests.append(request)
        self.log.append("service_start")
        yield ProgressEvent(kind="progress", message="working")
        yield ProgressEvent(kind="done", message="audit clean")


class _AnswerService:
    async def run(self, request: str):
        yield ProgressEvent(
            kind="done",
            message="read-only diff audit clean",
            answer="The repository purpose is documented in the root README.",
        )


def test_vibe_controller_defers_before_execution_and_posts_to_thread() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    controller = VibeController(_FakeService(log))

    asyncio.run(controller.handle(interaction, "inspect repo"))

    posted = "\n".join(interaction.thread.messages)
    assert log[0] == "defer"
    assert log.index("defer") < log.index("service_start")
    assert "Codex" in posted
    assert "COMPLETE" in posted
    assert "audit clean" in posted
    assert "message_edit" in log


def test_vibe_creates_non_invitable_private_thread_and_adds_requester() -> None:
    log: list[str] = []
    interaction = _Interaction(log)

    asyncio.run(VibeController(_FakeService(log)).handle(interaction, "inspect repo"))

    assert interaction.channel.created_kwargs["type"] == discord.ChannelType.private_thread
    assert interaction.channel.created_kwargs["invitable"] is False
    assert log.index("add_user") < log.index("service_start")


def test_vibe_rejects_user_outside_authorization_allowlist() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    interaction.user = SimpleNamespace(id=99, roles=[])
    service = _FakeService(log)

    asyncio.run(
        VibeController(service, allowed_user_ids={1}).handle(interaction, "inspect repo")
    )

    assert "create_thread" not in log
    assert "service_start" not in log
    assert service.requests == []
    assert any("not authorized" in message.lower() for message in interaction.followup.messages)


def test_vibe_controller_posts_worker_answer_with_terminal_evidence() -> None:
    log: list[str] = []
    interaction = _Interaction(log)

    asyncio.run(VibeController(_AnswerService()).handle(interaction, "inspect repo"))

    posted = "\n".join(interaction.thread.messages)
    assert "The repository purpose is documented in the root README." in posted
    assert "read-only diff audit clean" in posted


def test_vibe_progress_updates_one_status_message_in_place() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    controller = VibeController(_FakeService(log))

    asyncio.run(controller.handle(interaction, "inspect repo"))

    # Request + one mutable status card + one terminal evidence card.
    assert log.count("thread_send") == 3
    assert log.count("message_edit") == 2
    assert any("Worker:** Codex" in message for message in interaction.thread.messages)
    assert any("Evidence:** audit clean" in message for message in interaction.thread.messages)


class _MembershipFailThread(_Thread):
    async def add_user(self, user) -> None:
        self.log.append("add_user_failed")
        raise AttributeError("membership failed")


def test_vibe_membership_failure_is_visible_and_does_not_start_worker() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    failed_thread = _MembershipFailThread(log)
    interaction.thread = failed_thread
    interaction.channel = _Channel(log, failed_thread)
    service = _FakeService(log)
    controller = VibeController(service)

    asyncio.run(controller.handle(interaction, "inspect repo"))

    assert "service_start" not in log
    assert service.requests == []
    assert any("not started" in message.lower() for message in interaction.followup.messages)


def test_vibe_scrubs_request_before_worker_launch() -> None:
    from integrations.discord_command_center.scrub import SecretScrubber

    log: list[str] = []
    interaction = _Interaction(log)
    service = _FakeService(log)
    controller = VibeController(
        service,
        scrubber=SecretScrubber(secret_values=("discord-super-secret",)),
    )

    asyncio.run(controller.handle(interaction, "inspect discord-super-secret"))

    assert service.requests == ["inspect [REDACTED]"]


class _SecretOutputService:
    async def run(self, request: str):
        yield ProgressEvent(kind="progress", message="worker leaked discord-super-secret")
        yield ProgressEvent(kind="done", message="done")


def test_vibe_scrubs_worker_output_before_thread_send() -> None:
    from integrations.discord_command_center.scrub import SecretScrubber

    log: list[str] = []
    interaction = _Interaction(log)
    controller = VibeController(
        _SecretOutputService(),
        scrubber=SecretScrubber(secret_values=("discord-super-secret",)),
    )

    asyncio.run(controller.handle(interaction, "inspect repo"))

    rendered = "\n".join(interaction.thread.messages + interaction.thread.edit_history)
    assert "discord-super-secret" not in rendered
    assert "worker leaked [REDACTED]" in rendered


def test_secret_scrubber_redacts_env_values_and_key_shapes() -> None:
    from integrations.discord_command_center.scrub import SecretScrubber

    scrubber = SecretScrubber(
        secret_values=("discord-super-secret",),
    )
    text = (
        "token=discord-super-secret "
        "openai=sk-proj-AbCdEf1234567890 "
        "github=ghp_1234567890abcdefghij"
    )

    scrubbed = scrubber.scrub(text)

    assert "discord-super-secret" not in scrubbed
    assert "sk-proj-AbCdEf1234567890" not in scrubbed
    assert "ghp_1234567890abcdefghij" not in scrubbed
    assert scrubbed.count("[REDACTED]") == 3


def test_smoke_parser_defaults_to_readonly_prompt() -> None:
    from integrations.discord_command_center.smoke import build_parser

    args = build_parser().parse_args(["--repo", "/tmp/example"])

    assert args.repo == Path("/tmp/example")
    assert "read-only" in args.prompt.lower()
    assert args.timeout > 0


def test_worker_temp_directory_is_confined_to_run_worktree(tmp_path: Path) -> None:
    service, _ = _make_service(tmp_path, mutate=False)
    runner = service.runner

    asyncio.run(_collect(service.run("inspect repo")))

    assert isinstance(runner, _FakeRunner)
    _, cwd, environment, _ = runner.calls[0]
    runtime = cwd / ".command-center-runtime"
    assert environment["TMPDIR"] == str(runtime)
    assert environment["HOME"] == str(runtime)
    assert environment["CODEX_HOME"] == str(runtime)
    assert not runtime.exists()


class _ExplodingMutatingRunner:
    async def stream(self, command, *, cwd, environment, timeout_seconds):
        (cwd / "mutation-before-crash.txt").write_text("bad\n")
        raise RuntimeError("worker crashed")
        yield ProgressEvent(kind="progress", message="unreachable")


class _CancelledRunner:
    async def stream(self, command, *, cwd, environment, timeout_seconds):
        raise asyncio.CancelledError
        yield ProgressEvent(kind="progress", message="unreachable")


def test_service_preserves_cancellation_when_cleanup_and_audit_fail(
    tmp_path: Path, monkeypatch, caplog
) -> None:
    service, manager = _make_service(tmp_path, mutate=False)
    service.runner = _CancelledRunner()

    from integrations.discord_command_center.runtime import CodexRuntime

    def fail_runtime_cleanup(self) -> None:
        raise RuntimeError("runtime cleanup failed")

    def fail_audit(path: Path):
        raise RuntimeError("audit failed")

    monkeypatch.setattr(CodexRuntime, "cleanup", fail_runtime_cleanup)
    manager.audit = fail_audit  # type: ignore[method-assign]

    with pytest.raises(asyncio.CancelledError):
        asyncio.run(_collect(service.run("inspect repo")))

    assert "runtime cleanup failed" in caplog.text
    assert "audit failed" in caplog.text
    assert len(list(manager.run_root.glob("*"))) == 1


class _AnswerRunner:
    async def stream(self, command, *, cwd, environment, timeout_seconds):
        yield ProgressEvent(
            kind="progress",
            message=(
                '{"type":"item.completed","item":{"type":"agent_message",'
                '"text":"final repository answer"}}'
            ),
        )
        yield ProgressEvent(kind="process_exit", message="codex exited", exit_code=0)


def test_service_carries_worker_answer_into_terminal_event(tmp_path: Path) -> None:
    service, _ = _make_service(tmp_path, mutate=False)
    service.runner = _AnswerRunner()

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "done"
    assert events[-1].answer == "final repository answer"


def test_mutation_takes_precedence_over_runner_error(tmp_path: Path) -> None:
    service, manager = _make_service(tmp_path, mutate=False)
    service.runner = _ExplodingMutatingRunner()

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "failed"
    assert events[-1].code == "readonly_violation"
    preserved = list(manager.run_root.glob("*"))
    assert len(preserved) == 1
    assert (preserved[0] / "mutation-before-crash.txt").exists()


def test_unavailable_post_run_audit_fails_loud_and_preserves_worktree(tmp_path: Path) -> None:
    service, manager = _make_service(tmp_path, mutate=False)

    def fail_audit(path: Path):
        raise RuntimeError("git metadata unavailable")

    manager.audit = fail_audit  # type: ignore[method-assign]

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "failed"
    assert events[-1].code == "audit_unavailable"
    assert "post-run read-only audit unavailable" in events[-1].message
    assert len(list(manager.run_root.glob("*"))) == 1


def test_worktree_creation_failure_is_terminal(tmp_path: Path) -> None:
    class _FailingWorkspace:
        def create(self, run_id: str) -> Path:
            raise OSError("worktree root unavailable")

    service = VibeService(
        workspace=_FailingWorkspace(),  # type: ignore[arg-type]
        adapter=CodexAdapter(executable="/bin/echo", model="test-model"),
        runner=_FakeRunner(),
        timeout_seconds=9,
        environment={},
    )

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "failed"
    assert events[-1].code == "worktree_create_failed"
    assert "worktree root unavailable" in events[-1].message


def test_subprocess_runner_closes_worker_stdin(tmp_path: Path, monkeypatch) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    captured: dict[str, object] = {}

    class _Stdout:
        async def readline(self) -> bytes:
            return b""

    class _Process:
        stdout = _Stdout()
        returncode = 0

        async def wait(self) -> int:
            return 0

        def terminate(self) -> None:
            raise AssertionError("should not terminate")

        def kill(self) -> None:
            raise AssertionError("should not kill")

    async def fake_create(*args, **kwargs):
        captured.update(kwargs)
        return _Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    runner = SubprocessRunner()
    events = asyncio.run(
        _collect(
            runner.stream(
                ("/bin/echo", "ok"),
                cwd=tmp_path,
                environment={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
                timeout_seconds=1,
            )
        )
    )

    assert events[-1].exit_code == 0
    assert captured["stdin"] == asyncio.subprocess.DEVNULL
    assert captured["start_new_session"] is True


def test_subprocess_runner_timeout_covers_wait_after_stdout_closes(
    tmp_path: Path, monkeypatch
) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    class _ClosedStdout:
        async def readline(self) -> bytes:
            return b""

    class _Process:
        stdout = _ClosedStdout()
        returncode = None
        pid = 2468

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        async def wait(self) -> int:
            if self.terminated or self.killed:
                self.returncode = -15 if self.terminated else -9
                return self.returncode
            await asyncio.Event().wait()
            return 0

    process = _Process()

    async def fake_create(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    signals: list[tuple[int, int]] = []
    def signal_group(pid: int, sig: int) -> None:
        signals.append((pid, sig))
        process.terminated = sig == signal.SIGTERM
        process.killed = sig == signal.SIGKILL

    monkeypatch.setattr(os, "killpg", signal_group)
    events = asyncio.run(
        _collect(
            SubprocessRunner(kill_grace_seconds=0.01).stream(
                ("/bin/echo", "ok"),
                cwd=tmp_path,
                environment={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
                timeout_seconds=0.01,
            )
        )
    )

    assert signals == [(process.pid, signal.SIGTERM)]
    assert events[-1].code == "timeout"
    assert events[-1].exit_code == 124


def test_subprocess_runner_timeout_terminates_worker(tmp_path: Path, monkeypatch) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    class _BlockingStdout:
        async def readline(self) -> bytes:
            await asyncio.Event().wait()
            return b""

    class _Process:
        stdout = _BlockingStdout()
        returncode = None
        pid = 1234

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        async def wait(self) -> int:
            if self.terminated or self.killed:
                self.returncode = -15 if self.terminated else -9
                return self.returncode
            await asyncio.Event().wait()
            return 0

    process = _Process()

    async def fake_create(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    signals: list[tuple[int, int]] = []
    def signal_group(pid: int, sig: int) -> None:
        signals.append((pid, sig))
        process.terminated = sig == signal.SIGTERM
        process.killed = sig == signal.SIGKILL

    monkeypatch.setattr(os, "killpg", signal_group)
    runner = SubprocessRunner(kill_grace_seconds=0.01)
    events = asyncio.run(
        _collect(
            runner.stream(
                ("/bin/echo", "ok"),
                cwd=tmp_path,
                environment={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
                timeout_seconds=0.01,
            )
        )
    )

    assert signals == [(process.pid, signal.SIGTERM)]
    assert process.killed is False
    assert events[-1].code == "timeout"
    assert events[-1].exit_code == 124


def test_subprocess_runner_escalates_to_kill_after_grace_period(monkeypatch) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    class _StubbornProcess:
        returncode = None
        pid = 4321

        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        async def wait(self) -> int:
            if self.killed:
                self.returncode = -9
                return -9
            await asyncio.Event().wait()
            return 0

    process = _StubbornProcess()
    signals: list[tuple[int, int]] = []

    def signal_group(pid: int, sig: int) -> None:
        signals.append((pid, sig))
        process.killed = sig == signal.SIGKILL

    monkeypatch.setattr(os, "killpg", signal_group)
    runner = SubprocessRunner(kill_grace_seconds=0.01)

    asyncio.run(runner._terminate(process))

    assert signals == [(process.pid, signal.SIGTERM), (process.pid, signal.SIGKILL)]
    assert process.returncode == -9


@pytest.mark.parametrize("failure", [ValueError("oversized"), RuntimeError("read failed")])
def test_subprocess_runner_stdout_failure_terminates_process_group(
    failure: Exception, tmp_path: Path, monkeypatch
) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    class _BrokenStdout:
        async def readline(self) -> bytes:
            if isinstance(failure, ValueError):
                return b"x" * 32
            raise failure

    class _Process:
        stdout = _BrokenStdout()
        returncode = None
        pid = 6789

        async def wait(self) -> int:
            self.returncode = -15
            return self.returncode

    process = _Process()
    signals: list[tuple[int, int]] = []

    async def fake_create(*args, **kwargs):
        return process

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    monkeypatch.setattr(os, "killpg", lambda pid, sig: signals.append((pid, sig)))

    with pytest.raises((ValueError, RuntimeError)):
        asyncio.run(
            _collect(
                SubprocessRunner(kill_grace_seconds=0.01, max_line_bytes=16).stream(
                    ("/bin/echo", "ok"),
                    cwd=tmp_path,
                    environment={
                        "HOME": str(tmp_path),
                        "PATH": "/usr/bin:/bin",
                        "TMPDIR": str(tmp_path),
                    },
                    timeout_seconds=1,
                )
            )
        )

    assert signals == [(process.pid, signal.SIGTERM)]


def test_subprocess_runner_keeps_terminal_json_after_progress_limit(
    tmp_path: Path, monkeypatch
) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    answer = b'{"type":"item.completed","item":{"type":"agent_message","text":"answer"}}\n'

    class _Stdout:
        def __init__(self) -> None:
            self.lines = [b'{"type":"progress"}\n'] * 3 + [answer]

        async def readline(self) -> bytes:
            return self.lines.pop(0) if self.lines else b""

    class _Process:
        stdout = _Stdout()
        returncode = 0

        async def wait(self) -> int:
            return 0

    async def fake_create(*args, **kwargs):
        return _Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    events = asyncio.run(
        _collect(
            SubprocessRunner(max_lines=2).stream(
                ("/bin/echo", "ok"),
                cwd=tmp_path,
                environment={
                    "HOME": str(tmp_path),
                    "PATH": "/usr/bin:/bin",
                    "TMPDIR": str(tmp_path),
                },
                timeout_seconds=1,
            )
        )
    )

    assert any(event.message == answer.decode().rstrip() for event in events)
    assert events[-1].exit_code == 0


def test_subprocess_runner_reports_untrusted_terminal_evidence_after_progress_limit(
    tmp_path: Path, monkeypatch
) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    class _Stdout:
        def __init__(self) -> None:
            self.lines = [b"not-json\n"] * 3

        async def readline(self) -> bytes:
            return self.lines.pop(0) if self.lines else b""

    class _Process:
        stdout = _Stdout()
        returncode = 0

        async def wait(self) -> int:
            return 0

    async def fake_create(*args, **kwargs):
        return _Process()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
    events = asyncio.run(
        _collect(
            SubprocessRunner(max_lines=2).stream(
                ("/bin/echo", "ok"),
                cwd=tmp_path,
                environment={
                    "HOME": str(tmp_path),
                    "PATH": "/usr/bin:/bin",
                    "TMPDIR": str(tmp_path),
                },
                timeout_seconds=1,
            )
        )
    )

    assert events[-1].code == "terminal_evidence_untrusted"


def test_subprocess_runner_does_not_trust_started_agent_message_as_terminal_evidence() -> None:
    from integrations.discord_command_center.runner import _terminal_evidence

    started = b'{"type":"item.started","item":{"type":"agent_message","text":"not final"}}'
    completed = b'{"type":"item.completed","item":{"type":"agent_message","text":"final"}}'

    assert _terminal_evidence(started) is None
    assert _terminal_evidence(completed) == "answer"


def test_sandbox_profile_denies_host_reads_and_allows_runtime_paths(tmp_path: Path) -> None:
    profile = build_sandbox_profile(
        tmp_path,
        {"TMPDIR": str(tmp_path / "runtime"), "CODEX_AUTH_FILE": "/tmp/auth.json"},
    )

    assert "(deny file-read*)" in profile
    assert f'(allow file-read* (subpath "{tmp_path}"))' in profile
    assert f'(allow file-read* (literal "{Path("/tmp/auth.json").resolve()}"))' in profile


def test_sandbox_profile_allows_configured_codex_and_narrow_linked_git_metadata(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)
    manager = GitWorktreeManager(repo=repo, run_root=tmp_path / "runs")
    worktree = manager.create("sandbox-git-run")
    executable = "/Applications/ChatGPT.app/Contents/Resources/codex"

    profile = build_sandbox_profile(
        worktree, {"TMPDIR": str(worktree / "runtime")}, command=(executable,)
    )
    git_dir = Path(_git(worktree, "rev-parse", "--git-dir"))
    common_dir = Path(_git(worktree, "rev-parse", "--git-common-dir"))
    if not git_dir.is_absolute():
        git_dir = (worktree / git_dir).resolve()
    if not common_dir.is_absolute():
        common_dir = (worktree / common_dir).resolve()

    assert f'(allow file-read* (literal "{executable}"))' in profile
    assert f'(allow file-read* (subpath "{git_dir}"))' in profile
    assert f'(allow file-read* (subpath "{common_dir / "objects"}"))' in profile
    assert f'(allow file-read* (subpath "{common_dir}"))' not in profile
    assert f'(allow file-read* (subpath "{Path.home()}"))' not in profile
    assert 'allow file-read* (subpath "/")' not in profile


def test_sandbox_profile_uses_exact_codex_bundle_and_evidence_based_system_reads(
    tmp_path: Path,
) -> None:
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    codex = tmp_path / "ChatGPT.app" / "Contents" / "Resources" / "codex"
    codex.parent.mkdir(parents=True)
    codex.write_text("")
    (codex.parent / "rg").write_text("")
    auth = tmp_path / "codex-home" / "auth.json"
    auth.parent.mkdir()
    auth.write_text("{}")

    profile = build_sandbox_profile(
        worktree,
        {"TMPDIR": str(worktree / "runtime"), "CODEX_AUTH_FILE": str(auth)},
        command=(str(codex),),
    )

    assert f'(allow file-read* (literal "{codex}"))' in profile
    assert f'(allow file-read* (literal "{codex.parent / "rg"}"))' in profile
    assert f'(allow file-read* (literal "{auth}"))' in profile
    assert '(allow file-read* (subpath "/Library"))' not in profile
    assert '(allow file-read* (subpath "/opt/homebrew"))' not in profile
    assert '(allow file-read* (subpath "/usr/local/bin"))' not in profile
    assert '(allow file-read* (subpath "/System/Library"))' in profile
    assert '(allow file-read* (subpath "/usr/lib"))' in profile
    assert f'(allow file-read* (subpath "{Path.home()}"))' not in profile


def test_child_environment_default_path_stays_within_system_executable_roots() -> None:
    assert build_child_environment({})["PATH"] == "/usr/bin:/bin:/usr/sbin:/sbin"


def test_subprocess_runner_cancellation_terminates_worker(tmp_path: Path, monkeypatch) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    async def exercise() -> tuple[bool, bool]:
        created = asyncio.Event()

        class _BlockingStdout:
            async def readline(self) -> bytes:
                await asyncio.Event().wait()
                return b""

        class _Process:
            stdout = _BlockingStdout()
            returncode = None
            pid = 5678

            def __init__(self) -> None:
                self.terminated = False
                self.killed = False

            def terminate(self) -> None:
                self.terminated = True

            def kill(self) -> None:
                self.killed = True

            async def wait(self) -> int:
                if self.terminated or self.killed:
                    self.returncode = -15 if self.terminated else -9
                    return self.returncode
                await asyncio.Event().wait()
                return 0

        process = _Process()

        async def fake_create(*args, **kwargs):
            created.set()
            return process

        monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_create)
        signals: list[tuple[int, int]] = []

        def signal_group(pid: int, sig: int) -> None:
            signals.append((pid, sig))
            process.terminated = sig == signal.SIGTERM
            process.killed = sig == signal.SIGKILL

        monkeypatch.setattr(os, "killpg", signal_group)
        runner = SubprocessRunner(kill_grace_seconds=0.01)
        task = asyncio.create_task(
            _collect(
                runner.stream(
                    ("/bin/echo", "ok"),
                    cwd=tmp_path,
                    environment={
                        "HOME": str(tmp_path),
                        "PATH": "/usr/bin:/bin",
                        "TMPDIR": str(tmp_path),
                    },
                    timeout_seconds=30,
                )
            )
        )
        await created.wait()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return bool(signals), process.killed

    terminated, killed = asyncio.run(exercise())

    assert terminated is True
    assert killed is False


@pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is macOS-specific")
def test_sandbox_profile_allows_worktree_only_and_dev_null(tmp_path: Path) -> None:
    from integrations.discord_command_center.runner import build_sandbox_profile

    runtime = tmp_path / "runtime"
    runtime.mkdir()
    outside = tmp_path.parent / f"{tmp_path.name}-outside"
    profile = build_sandbox_profile(tmp_path, {"TMPDIR": str(runtime)})

    inside_result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", profile, "/usr/bin/touch", str(tmp_path / "inside")],
        capture_output=True,
        text=True,
    )
    dev_null_result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", profile, "/bin/sh", "-c", "echo ok >/dev/null"],
        capture_output=True,
        text=True,
    )
    outside_result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", profile, "/usr/bin/touch", str(outside)],
        capture_output=True,
        text=True,
    )

    assert inside_result.returncode == 0
    assert dev_null_result.returncode == 0
    assert outside_result.returncode != 0
    assert (tmp_path / "inside").exists()
    assert not outside.exists()


def test_plaintext_child_output_is_not_forwarded_verbatim() -> None:
    from integrations.discord_command_center.service import _format_codex_progress

    rendered = _format_codex_progress("/bin/zsh -lc secret-looking-command")

    assert rendered == "Codex is working…"
    assert "secret-looking-command" not in rendered


def test_codex_command_execution_progress_is_semantic_not_raw() -> None:
    import json

    from integrations.discord_command_center.service import _format_codex_progress

    event = json.dumps(
        {
            "type": "item.completed",
            "item": {"type": "command_execution", "command": "/bin/zsh -lc secret-looking-command"},
        }
    )

    rendered = _format_codex_progress(event)

    assert rendered == "Inspecting repository…"
    assert "secret-looking-command" not in rendered


def test_vibe_keeps_all_thread_content_within_discord_limit() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    service = _FakeService(log)
    controller = VibeController(service, status_interval_seconds=0)

    asyncio.run(controller.handle(interaction, "x" * 5000))

    rendered = interaction.thread.messages + interaction.thread.edit_history
    assert rendered
    assert max(map(len, rendered)) <= 1900


class _BurstProgressService:
    async def run(self, request: str):
        yield ProgressEvent(kind="progress", message="x" * 5000)
        yield ProgressEvent(kind="progress", message="step two")
        yield ProgressEvent(kind="progress", message="step three")
        yield ProgressEvent(kind="done", message="audit clean")


def test_vibe_throttles_burst_progress_status_edits() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    controller = VibeController(_BurstProgressService(), status_interval_seconds=9999)

    asyncio.run(controller.handle(interaction, "inspect repo"))

    # One progress edit is allowed; burst duplicates are coalesced, then terminal state is shown.
    assert log.count("message_edit") == 2
    assert max(map(len, interaction.thread.edit_history)) <= 1900
    assert "step two" not in "\n".join(interaction.thread.edit_history)
    assert "step three" not in "\n".join(interaction.thread.edit_history)
    assert "COMPLETE" in interaction.thread.messages[1]


@pytest.mark.skipif(sys.platform != "darwin", reason="sandbox-exec is macOS-specific")
def test_sandbox_profile_denies_symlink_write_escape(tmp_path: Path) -> None:
    from integrations.discord_command_center.runner import build_sandbox_profile

    worktree = tmp_path / "worktree"
    runtime = worktree / "runtime"
    runtime.mkdir(parents=True)
    outside = tmp_path / "outside.txt"
    outside.write_text("safe\n")
    escape = worktree / "escape.txt"
    escape.symlink_to(outside)
    profile = build_sandbox_profile(worktree, {"TMPDIR": str(runtime)})

    result = subprocess.run(
        ["/usr/bin/sandbox-exec", "-p", profile, "/bin/sh", "-c", f'echo PWNED > "{escape}"'],
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert outside.read_text() == "safe\n"


def test_secret_scrubber_redacts_named_secret_assignments() -> None:
    from integrations.discord_command_center.scrub import SecretScrubber

    scrubbed = SecretScrubber().scrub(
        "repo secret: INTERNAL_DB_PASSWORD=hunter2-longer Authorization: Bearer abcdefghijklmnop"
    )

    assert "hunter2-longer" not in scrubbed
    assert "abcdefghijklmnop" not in scrubbed
    assert "INTERNAL_DB_PASSWORD=[REDACTED]" in scrubbed
    assert "Authorization: [REDACTED]" in scrubbed


def test_secret_scrubber_redacts_fine_grained_and_quoted_tokens() -> None:
    from integrations.discord_command_center.scrub import SecretScrubber

    scrubbed = SecretScrubber().scrub(
        "github_pat_11ABCDEFG1234567890abcdef "
        "DATABASE_PASSWORD=\"hunter2-longer\" API_KEY='abcdefghijklmnop'"
    )

    assert "github_pat_11ABCDEFG1234567890abcdef" not in scrubbed
    assert 'DATABASE_PASSWORD="hunter2-longer"' not in scrubbed
    assert "API_KEY='abcdefghijklmnop'" not in scrubbed
    assert 'DATABASE_PASSWORD="[REDACTED]"' in scrubbed
    assert "API_KEY='[REDACTED]'" in scrubbed


class _NamedSecretOutputService:
    async def run(self, request: str):
        yield ProgressEvent(
            kind="progress",
            message="repo secret: INTERNAL_DB_PASSWORD=hunter2-longer",
        )
        yield ProgressEvent(kind="done", message="audit clean")


def test_vibe_dlp_blocks_named_repository_secret_from_thread() -> None:
    from integrations.discord_command_center.scrub import SecretScrubber

    log: list[str] = []
    interaction = _Interaction(log)
    controller = VibeController(
        _NamedSecretOutputService(),
        scrubber=SecretScrubber(),
        status_interval_seconds=0,
    )

    asyncio.run(controller.handle(interaction, "inspect repo"))

    rendered = "\n".join(interaction.thread.messages + interaction.thread.edit_history)
    assert "hunter2-longer" not in rendered
    assert "INTERNAL_DB_PASSWORD=[REDACTED]" in rendered
