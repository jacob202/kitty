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

    assert process.terminated is True
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


def test_plaintext_child_output_is_not_forwarded_verbatim() -> None:
    from integrations.discord_command_center.service import _format_codex_progress

    rendered = _format_codex_progress("/bin/zsh -lc secret-looking-command")

    assert rendered == "Codex is working…"
    assert "secret-looking-command" not in rendered


def test_codex_command_execution_progress_is_semantic_not_raw() -> None:
    import json

    from integrations.discord_command_center.service import _format_codex_progress

    event = json.dumps({
        "type": "item.completed",
        "item": {"type": "command_execution", "command": "/bin/zsh -lc secret-looking-command"},
    })

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
