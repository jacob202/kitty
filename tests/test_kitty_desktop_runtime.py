import signal

from scripts import kitty_desktop_runtime as rt


def test_stop_waits_until_owned_process_has_exited(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "PID_DIR", tmp_path / "run")
    monkeypatch.setattr(rt, "LOG_FILE", tmp_path / "desktop.log")
    monkeypatch.setattr(rt, "ROOT", tmp_path / "kitty")
    rt.ROOT.mkdir()
    rt.write_pid("gateway", 4321)

    state = {"alive": True, "stopping": False, "post_stop_probes": 0}

    def fake_kill(pid, sig):
        assert pid == 4321
        if sig == 0:
            if not state["alive"]:
                raise ProcessLookupError
            if state["stopping"]:
                state["post_stop_probes"] += 1
                if state["post_stop_probes"] >= 2:
                    state["alive"] = False
                    raise ProcessLookupError
            return None
        raise AssertionError(f"unexpected signal {sig}")

    def fake_killpg(pid, sig):
        assert (pid, sig) == (4321, signal.SIGTERM)
        state["stopping"] = True

    monkeypatch.setattr(rt.os, "kill", fake_kill)
    monkeypatch.setattr(rt.os, "killpg", fake_killpg)
    monkeypatch.setattr(rt.time, "sleep", lambda _: None)
    monkeypatch.setattr(rt, "pid_owned_by_runtime", lambda name, pid: True, raising=False)

    assert rt.stop_name("gateway") is True
    assert state["alive"] is False
    assert not rt.pid_file("gateway").exists()


def test_stop_refuses_pidfile_process_it_cannot_prove_it_owns(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "PID_DIR", tmp_path / "run")
    monkeypatch.setattr(rt, "LOG_FILE", tmp_path / "desktop.log")
    rt.write_pid("gateway", 7331)
    monkeypatch.setattr(rt.os, "kill", lambda pid, sig: None)
    monkeypatch.setattr(rt, "pid_owned_by_runtime", lambda name, pid: False, raising=False)

    sent = []
    monkeypatch.setattr(rt.os, "killpg", lambda pid, sig: sent.append((pid, sig)))

    assert rt.stop_name("gateway") is False
    assert sent == []
    assert not rt.pid_file("gateway").exists()


def test_ensure_rechecks_transiently_healthy_gateway_before_success(monkeypatch):
    gateway_ensures = []

    def fake_ensure_gateway():
        gateway_ensures.append(len(gateway_ensures) + 1)
        return None if len(gateway_ensures) == 1 else 9001

    health_results = iter([False, True, True])
    monkeypatch.setattr(rt, "ensure_gateway", fake_ensure_gateway)
    monkeypatch.setattr(rt, "ensure_ui", lambda: None)
    monkeypatch.setattr(rt, "wait_for_http", lambda url: next(health_results), raising=False)
    monkeypatch.setattr(rt, "read_pid", lambda name: 9001 if name == "gateway" else None)

    result = rt.ensure_all()

    assert gateway_ensures == [1, 2]
    assert result["ok"] is True
    assert result["gateway_healthy"] is True
    assert result["ui_healthy"] is True
