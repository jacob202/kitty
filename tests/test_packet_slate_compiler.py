import json
import subprocess
import sys
from pathlib import Path


def _source() -> dict:
    return {
        "manifest_version": 1,
        "initiative_id": "demo-v1",
        "title": "Demo slate",
        "description": "Demo",
        "base_sha": "a" * 40,
        "packets": [
            {
                "manifest": {
                    "id": "DEMO-01",
                    "title": "Do the thing",
                    "objective": "Change only the declared files.",
                    "depends_on": [],
                    "acceptance_criteria": ["The declared pytest gate passes."],
                    "allowed_paths": ["gateway/demo.py", "tests/test_demo.py"],
                    "policy": {"max_attempts": 2, "priority": 10},
                    "validation_commands": ["python -m pytest -q tests/test_demo.py"],
                },
                "finding": "The thing is unreachable.",
                "stop": "Stop if another subsystem is required.",
                "recovery": "Source and tests only.",
            }
        ],
    }


def test_compiler_emits_manifest_and_companion_doc(tmp_path: Path):
    source = tmp_path / "source.json"
    manifest = tmp_path / "initiative.json"
    packet_dir = tmp_path / "packets"
    source.write_text(json.dumps(_source()), encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "scripts/packet_slate_compiler.py",
            str(source),
            "--manifest-out",
            str(manifest),
            "--packet-dir",
            str(packet_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    emitted = json.loads(manifest.read_text(encoding="utf-8"))
    assert emitted["initiative_id"] == "demo-v1"
    assert [packet["id"] for packet in emitted["packets"]] == ["DEMO-01"]
    assert "base_sha" not in emitted
    doc = (packet_dir / "DEMO-01.md").read_text(encoding="utf-8")
    assert "**Owner:** builder" in doc
    assert "The thing is unreachable." in doc
    assert "python -m pytest -q tests/test_demo.py" in doc


def _run_compiler(tmp_path: Path, payload: dict) -> subprocess.CompletedProcess[str]:
    source = tmp_path / "source.json"
    source.write_text(json.dumps(payload), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            "scripts/packet_slate_compiler.py",
            str(source),
            "--manifest-out",
            str(tmp_path / "initiative.json"),
            "--packet-dir",
            str(tmp_path / "packets"),
        ],
        text=True,
        capture_output=True,
        check=False,
    )


def test_compiler_rejects_paid_routing(tmp_path: Path):
    payload = _source()
    payload["packets"][0]["manifest"]["policy"]["routing"] = {"model": "paid"}
    completed = _run_compiler(tmp_path, payload)
    assert completed.returncode != 0
    assert "routing" in completed.stderr.lower()


def test_compiler_rejects_node_validation_for_builder_packet(tmp_path: Path):
    payload = _source()
    payload["packets"][0]["manifest"]["validation_commands"] = ["npx vitest run"]
    completed = _run_compiler(tmp_path, payload)
    assert completed.returncode != 0
    assert "node" in completed.stderr.lower()


def test_compiler_rejects_unknown_manifest_key(tmp_path: Path):
    payload = _source()
    payload["packets"][0]["manifest"]["mystery"] = True
    completed = _run_compiler(tmp_path, payload)
    assert completed.returncode != 0
    assert "unknown" in completed.stderr.lower()


def test_interactive_packet_emits_doc_but_not_manifest_entry(tmp_path: Path):
    payload = _source()
    entry = payload["packets"][0]
    entry["lane"] = "interactive"
    entry["manifest"]["validation_commands"] = ["npx vitest run tests/Demo.test.tsx"]
    completed = _run_compiler(tmp_path, payload)

    assert completed.returncode == 0, completed.stderr
    emitted = json.loads((tmp_path / "initiative.json").read_text(encoding="utf-8"))
    assert emitted["packets"] == []
    doc = (tmp_path / "packets" / "DEMO-01.md").read_text(encoding="utf-8")
    assert "**Owner:** interactive" in doc
    assert "**Builder manifest:** none" in doc
    assert "npx vitest run tests/Demo.test.tsx" in doc


def test_compiler_rejects_unknown_lane(tmp_path: Path):
    payload = _source()
    payload["packets"][0]["lane"] = "mystery"
    completed = _run_compiler(tmp_path, payload)
    assert completed.returncode != 0
    assert "lane" in completed.stderr.lower()


def test_held_builder_packet_emits_doc_but_not_manifest_entry(tmp_path: Path):
    payload = _source()
    entry = payload["packets"][0]
    entry["lane"] = "held"
    entry["hold_reason"] = "Active PR owns gateway/app.py."
    completed = _run_compiler(tmp_path, payload)

    assert completed.returncode == 0, completed.stderr
    emitted = json.loads((tmp_path / "initiative.json").read_text(encoding="utf-8"))
    assert emitted["packets"] == []
    doc = (tmp_path / "packets" / "DEMO-01.md").read_text(encoding="utf-8")
    assert "**Owner:** builder (held)" in doc
    assert "**Builder manifest:** held" in doc
    assert "Active PR owns gateway/app.py." in doc
