from __future__ import annotations

import inspect

from gateway import builder_run as br
from gateway.operating_policy import PolicyDecision


def test_initiative_effectiveness_guard_is_default_on():
    parameter = inspect.signature(br.run_initiative).parameters["effectiveness_guard"]

    assert parameter.default is True


def test_effectiveness_metrics_keep_unknown_measurements_unknown(monkeypatch):
    monkeypatch.setattr(br.time, "monotonic", lambda: 500.0)

    metrics = br._effectiveness_metrics(
        campaign_started=100.0,
        packet_started=350.0,
        processed_packets=2,
        accepted_packets=1,
    )

    assert metrics["elapsed_seconds"] == 400.0
    assert metrics["current_packet_elapsed_seconds"] == 150.0
    assert metrics["processed_packets"] == 2
    assert metrics["accepted_packets"] == 1
    assert metrics["worker_tokens"] is None
    assert metrics["setup_metadata_seconds"] is None


def test_effectiveness_pause_is_durable(monkeypatch):
    paused = []
    decisions = []
    monkeypatch.setattr(br.time, "monotonic", lambda: 5000.0)
    monkeypatch.setattr(
        br.op,
        "evaluate_builder_campaign",
        lambda metrics: PolicyDecision(
            "pause",
            ("accepted-packet throughput is below policy",),
            ("worker_tokens",),
        ),
    )
    monkeypatch.setattr(
        br.bi,
        "pause_initiative",
        lambda initiative_id, reason, db_path=None: paused.append(
            (initiative_id, reason, db_path)
        ),
    )
    monkeypatch.setattr(
        br,
        "_decide",
        lambda task_id, payload, db_path: decisions.append(
            (task_id, payload, db_path)
        ),
    )

    result = br._effectiveness_pause(
        "initiative-1",
        "packet-2",
        "task-2",
        campaign_started=1000.0,
        packet_started=4500.0,
        processed_packets=2,
        accepted_packets=1,
        db_path=None,
    )

    assert result is not None
    assert result["outcome"] == "paused"
    assert paused and paused[0][0] == "initiative-1"
    assert decisions[0][1]["decision"] == "effectiveness_paused"
    assert decisions[0][1]["metrics"]["processed_packets"] == 2


def test_run_initiative_stops_when_effectiveness_guard_trips(monkeypatch):
    packet = {"packet_id": "packet-1", "task_id": "task-1"}
    monkeypatch.setattr(br.bi, "init_db", lambda db_path=None: None)
    monkeypatch.setattr(br.bq, "recover_expired_leases", lambda db_path=None: [])
    monkeypatch.setattr(br.bq, "recover_interrupted_runs", lambda db_path=None: [])
    monkeypatch.setattr(
        br.bi,
        "get_initiative_state",
        lambda initiative_id, db_path=None: "running",
    )
    monkeypatch.setattr(
        br.bi,
        "next_packet",
        lambda initiative_id, db_path=None: packet,
    )
    monkeypatch.setattr(
        br.bl,
        "run_packet",
        lambda *args, **kwargs: {"outcome": "succeeded", "attempts": []},
    )
    monkeypatch.setattr(br, "_decide", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        br,
        "_effectiveness_pause",
        lambda *args, **kwargs: {
            "outcome": "paused",
            "reason": "Builder effectiveness guard: packet too slow",
            "stop_class": br.STOP_ROUTINE,
            "effectiveness": {"status": "pause"},
        },
    )

    result = br.run_initiative(
        "initiative-1",
        worker_command=["worker"],
    )

    assert result["outcome"] == "paused"
    assert result["succeeded"] == 1
    assert result["processed"] == [
        {
            "packet_id": "packet-1",
            "task_id": "task-1",
            "outcome": "succeeded",
        }
    ]
