from __future__ import annotations

from contextlib import contextmanager


def test_cleanup_project_is_idempotent_when_project_is_already_missing(monkeypatch) -> None:
    from gateway import project_store
    from gateway.tests import e2e_cleanup

    def missing_project(_project_id: int, **_fields):
        raise project_store.ProjectNotFound("already gone")

    class FakeConn:
        def __init__(self) -> None:
            self.executed: list[tuple[str, tuple[int]]] = []
            self.committed = False

        def execute(self, sql: str, params: tuple[int]):
            self.executed.append((sql, params))
            return self

        def commit(self) -> None:
            self.committed = True

    conn = FakeConn()

    @contextmanager
    def fake_connect(_db_file):
        yield conn

    monkeypatch.setattr(project_store, "update_fields", missing_project)
    monkeypatch.setattr(e2e_cleanup.db, "migrate", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(e2e_cleanup.db, "connect", fake_connect)

    e2e_cleanup.cleanup_project(999)

    assert conn.committed is True
    assert conn.executed
    assert conn.executed[0][1] == (999,)
