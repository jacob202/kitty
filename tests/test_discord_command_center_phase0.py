from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

import pytest

from integrations.discord_command_center.adapters.codex import CodexAdapter
from integrations.discord_command_center.bot import VibeController, split_discord_message
from integrations.discord_command_center.models import ProgressEvent
from integrations.discord_command_center.runner import build_child_environment
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
        "PATH": "/usr/bin:/bin",
        "LANG": "en_CA.UTF-8",
        "TERM": "xterm-256color",
        "CODEX_HOME": "/Users/test/.codex",
        "OPENAI_API_KEY": "sk-secret",
        "DISCORD_BOT_TOKEN": "discord-secret",
        "COMMAND_CENTER_DISCORD_TOKEN": "another-secret",
    }

    child = build_child_environment(source)

    assert child["HOME"] == "/Users/test"
    assert child["PATH"] == "/usr/bin:/bin"
    assert child["CODEX_HOME"] == "/Users/test/.codex"
    assert "OPENAI_API_KEY" not in child
    assert "DISCORD_BOT_TOKEN" not in child
    assert "COMMAND_CENTER_DISCORD_TOKEN" not in child


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


class _Thread:
    mention = "<#thread>"

    def __init__(self, log: list[str]) -> None:
        self.log = log
        self.messages: list[str] = []

    async def add_user(self, user) -> None:
        self.log.append("add_user")

    async def send(self, content: str) -> None:
        self.log.append("thread_send")
        self.messages.append(content)


class _Channel:
    def __init__(self, log: list[str], thread: _Thread) -> None:
        self.log = log
        self.thread = thread

    async def create_thread(self, **kwargs):
        self.log.append("create_thread")
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


def test_vibe_controller_defers_before_execution_and_posts_to_thread() -> None:
    log: list[str] = []
    interaction = _Interaction(log)
    controller = VibeController(_FakeService(log))

    asyncio.run(controller.handle(interaction, "inspect repo"))

    assert log[0] == "defer"
    assert log.index("defer") < log.index("service_start")
    assert "working" in "\n".join(interaction.thread.messages)
    assert "audit clean" in "\n".join(interaction.thread.messages)


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

    posted = "\n".join(interaction.thread.messages)
    assert "discord-super-secret" not in posted
    assert "worker leaked [REDACTED]" in posted


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


def test_mutation_takes_precedence_over_runner_error(tmp_path: Path) -> None:
    service, manager = _make_service(tmp_path, mutate=False)
    service.runner = _ExplodingMutatingRunner()

    events = asyncio.run(_collect(service.run("inspect repo")))

    assert events[-1].kind == "failed"
    assert events[-1].code == "readonly_violation"
    preserved = list(manager.run_root.glob("*"))
    assert len(preserved) == 1
    assert (preserved[0] / "mutation-before-crash.txt").exists()


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


def test_subprocess_runner_timeout_terminates_worker(tmp_path: Path, monkeypatch) -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    class _BlockingStdout:
        async def readline(self) -> bytes:
            await asyncio.Event().wait()
            return b""

    class _Process:
        stdout = _BlockingStdout()
        returncode = None

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

    assert process.terminated is True
    assert process.killed is False
    assert events[-1].code == "timeout"
    assert events[-1].exit_code == 124


def test_subprocess_runner_escalates_to_kill_after_grace_period() -> None:
    from integrations.discord_command_center.runner import SubprocessRunner

    class _StubbornProcess:
        returncode = None

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
    runner = SubprocessRunner(kill_grace_seconds=0.01)

    asyncio.run(runner._terminate(process))

    assert process.terminated is True
    assert process.killed is True
    assert process.returncode == -9


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
        runner = SubprocessRunner(kill_grace_seconds=0.01)
        task = asyncio.create_task(
            _collect(
                runner.stream(
                    ("/bin/echo", "ok"),
                    cwd=tmp_path,
                    environment={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin", "TMPDIR": str(tmp_path)},
                    timeout_seconds=30,
                )
            )
        )
        await created.wait()
        await asyncio.sleep(0)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return process.terminated, process.killed

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
