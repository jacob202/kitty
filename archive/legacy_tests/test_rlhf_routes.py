import json

from flask import Flask

from src.api.streaming_routes import streaming_bp


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(streaming_bp)
    return app


def test_rlhf_options_returns_deterministic_options(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = _make_app().test_client()

    response = client.post(
        "/api/rlhf/options",
        json={"query": "Sansui hums on startup", "count": 3},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["query"] == "Sansui hums on startup"
    assert [option["id"] for option in payload["options"]] == ["opt-1", "opt-2", "opt-3"]
    assert payload["options"][0]["label"] == "direct"


def test_rlhf_preference_stores_pairs(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    client = _make_app().test_client()
    options = client.post(
        "/api/rlhf/options",
        json={"query": "Ridgeline has a rattle", "count": 3},
    ).get_json()["options"]

    response = client.post(
        "/api/rlhf/preference",
        json={
            "query": "Ridgeline has a rattle",
            "options": options,
            "chosen_id": "opt-2",
            "metadata": {"source": "test"},
        },
    )

    assert response.status_code == 200
    assert response.get_json() == {"ok": True, "pairs_stored": 2}

    store = tmp_path / "data" / "rlhf" / "preferences.jsonl"
    records = [json.loads(line) for line in store.read_text().splitlines()]
    assert len(records) == 2
    assert {record["rejected_id"] for record in records} == {"opt-1", "opt-3"}
    assert all(record["chosen_id"] == "opt-2" for record in records)
