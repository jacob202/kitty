"""Tests for the live Builder worker event/state vocabulary."""

from gateway.builder_worker_session import WorkerEvent, WorkerEventType, WorkerState


def test_worker_event_taxonomy_is_stable():
    expected = {
        "session_started", "session_resumed", "brief_delivered", "instruction_sent",
        "text_delta", "message_complete", "tool_start", "tool_end", "command_start",
        "command_end", "file_change", "commit", "model_switch", "provider_switch",
        "usage", "attention_request", "permission_request", "heartbeat", "idle",
        "error", "cancelled", "session_ended", "raw",
    }
    assert {item.value for item in WorkerEventType} == expected


def test_worker_event_defaults_and_payload():
    event = WorkerEvent(event_id="ev1", seq=0, data={"text": "hello"})
    assert event.type == WorkerEventType.RAW
    assert event.data == {"text": "hello"}
    assert event.raw_payload is None


def test_worker_states_are_stable():
    assert {item.value for item in WorkerState} == {
        "starting", "running", "idle", "completed", "cancelled", "failed", "disposed"
    }
