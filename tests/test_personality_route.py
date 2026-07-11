from fastapi import FastAPI
from fastapi.testclient import TestClient

from gateway.routes import personality


def test_personality_route_reads_and_updates_both_config_files(tmp_path, monkeypatch):
    soul_file = tmp_path / "SOUL.md"
    preferences_file = tmp_path / "PREFERENCES.md"
    soul_file.write_text("original soul\n", encoding="utf-8")
    preferences_file.write_text("- original preference\n", encoding="utf-8")
    monkeypatch.setattr(personality, "SOUL_FILE", soul_file)
    monkeypatch.setattr(personality, "PREFERENCES_FILE", preferences_file)

    app = FastAPI()
    app.include_router(personality.router)
    client = TestClient(app)

    assert client.get("/settings/personality").json() == {
        "soul": "original soul\n",
        "preferences": "- original preference\n",
    }

    response = client.put(
        "/settings/personality",
        json={"soul": "direct but kind", "preferences": "- keep it brief"},
    )

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert soul_file.read_text(encoding="utf-8") == "direct but kind\n"
    assert preferences_file.read_text(encoding="utf-8") == "- keep it brief\n"


def test_personality_route_rejects_blank_content(tmp_path, monkeypatch):
    soul_file = tmp_path / "SOUL.md"
    preferences_file = tmp_path / "PREFERENCES.md"
    soul_file.write_text("original soul\n", encoding="utf-8")
    preferences_file.write_text("- original preference\n", encoding="utf-8")
    monkeypatch.setattr(personality, "SOUL_FILE", soul_file)
    monkeypatch.setattr(personality, "PREFERENCES_FILE", preferences_file)

    app = FastAPI()
    app.include_router(personality.router)
    client = TestClient(app)

    response = client.put(
        "/settings/personality",
        json={"soul": " ", "preferences": "- keep it brief"},
    )

    assert response.status_code == 422
    assert soul_file.read_text(encoding="utf-8") == "original soul\n"


def test_personality_route_rolls_back_soul_when_preferences_replace_fails(tmp_path, monkeypatch):
    soul_file = tmp_path / "SOUL.md"
    preferences_file = tmp_path / "PREFERENCES.md"
    soul_file.write_text("original soul\n", encoding="utf-8")
    preferences_file.write_text("- original preference\n", encoding="utf-8")
    monkeypatch.setattr(personality, "SOUL_FILE", soul_file)
    monkeypatch.setattr(personality, "PREFERENCES_FILE", preferences_file)

    real_replace = personality.os.replace
    calls = 0

    def fail_second_replace(source, target):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("simulated preferences write failure")
        return real_replace(source, target)

    monkeypatch.setattr(personality.os, "replace", fail_second_replace)
    app = FastAPI()
    app.include_router(personality.router)

    response = TestClient(app, raise_server_exceptions=False).put(
        "/settings/personality",
        json={"soul": "new soul", "preferences": "- new preference"},
    )

    assert response.status_code == 500
    assert soul_file.read_text(encoding="utf-8") == "original soul\n"
    assert preferences_file.read_text(encoding="utf-8") == "- original preference\n"
