"""Tests for the unified CommandEngine."""

import pytest
from src.core.command_engine import CommandEngine, CommandResult, get_command_engine


@pytest.fixture
def engine():
    return CommandEngine()


class TestCommandEngine:
    def test_register_and_execute(self, engine):
        def echo_handler(args, **ctx):
            return CommandResult(success=True, message=f"echo: {args}", data={"args": args})

        engine.register("echo", echo_handler, description="Echo back arguments")
        result = engine.execute("/echo hello world")
        assert result.success
        assert result.message == "echo: hello world"
        assert result.data["args"] == "hello world"

    def test_unknown_command(self, engine):
        result = engine.execute("/nonexistent")
        assert not result.success
        assert "Unknown command" in result.error

    def test_unknown_command_no_prefix(self, engine):
        result = engine.execute("hello")
        assert not result.success

    def test_command_with_slash_prefix(self, engine):
        def h(args, **ctx):
            return CommandResult(success=True, message="ok")

        engine.register("test", h)
        result = engine.execute("/test")
        assert result.success

    def test_help_only_visible(self, engine):
        engine.register("visible1", lambda a, **c: CommandResult(True, "ok"), description="First", visible=True)
        engine.register("hidden", lambda a, **c: CommandResult(True, "ok"), description="Secret", visible=False)
        engine.register("visible2", lambda a, **c: CommandResult(True, "ok"), description="Second", visible=True)

        help_text = engine.get_help()
        assert "/visible1" in help_text
        assert "/visible2" in help_text
        assert "/hidden" not in help_text

    def test_visible_count(self, engine):
        engine.register("a", lambda a, **c: CommandResult(True, "ok"), visible=True)
        engine.register("b", lambda a, **c: CommandResult(True, "ok"), visible=False)
        engine.register("c", lambda a, **c: CommandResult(True, "ok"), visible=True)
        assert engine.visible_count() == 2

    def test_command_names(self, engine):
        engine.register("foo", lambda a, **c: CommandResult(True, "ok"))
        engine.register("bar", lambda a, **c: CommandResult(True, "ok"))
        names = engine.command_names()
        assert "foo" in names
        assert "bar" in names

    def test_get_similar(self, engine):
        engine.register("status", lambda a, **c: CommandResult(True, "ok"))
        engine.register("stuck", lambda a, **c: CommandResult(True, "ok"))
        similar = engine.get_similar("statuz")
        assert "status" in similar

    def test_get_similar_no_match(self, engine):
        engine.register("status", lambda a, **c: CommandResult(True, "ok"))
        similar = engine.get_similar("xyzzy", cutoff=0.8)
        assert similar == []

    def test_handler_error(self, engine):
        def bad_handler(args, **ctx):
            raise RuntimeError("boom")

        engine.register("bad", bad_handler)
        result = engine.execute("/bad")
        assert not result.success
        assert "Error processing command" in result.error

    def test_stdout_mode(self, engine, capsys):
        engine.register("hi", lambda a, **c: CommandResult(True, "hello"))
        result = engine.execute("/hi", output_mode="stdout")
        assert result.success
        captured = capsys.readouterr()
        assert "hello" in captured.out

    def test_stdout_mode_error(self, engine, capsys):
        result = engine.execute("/nope", output_mode="stdout")
        captured = capsys.readouterr()
        assert "Unknown command" in captured.out

    def test_context_passed_to_handler(self, engine):
        def handler(args, **ctx):
            return CommandResult(
                success=True,
                message=f"sup={ctx.get('sup', 'none')}, orch={ctx.get('orch', 'none')}",
            )

        engine.register("ctx", handler)
        result = engine.execute("/ctx", output_mode="dict", sup="my_sup", orch="my_orch")
        assert "sup=my_sup" in result.message
        assert "orch=my_orch" in result.message

    def test_result_to_api_dict(self):
        result = CommandResult(success=True, message="ok", data={"key": "val"})
        d = result.to_api_dict()
        assert d["ok"] is True
        assert d["response"] == "ok"
        assert d["data"]["key"] == "val"

        fail = CommandResult(success=False, error="failed")
        d = fail.to_api_dict()
        assert d["ok"] is False
        assert d["response"] == "failed"

    def test_get_command_engine_singleton(self):
        e1 = get_command_engine()
        e2 = get_command_engine()
        assert e1 is e2

    def test_register_overwrites(self, engine):
        engine.register("dup", lambda a, **c: CommandResult(True, "first"))
        engine.register("dup", lambda a, **c: CommandResult(True, "second"))
        result = engine.execute("/dup")
        assert result.message == "second"
