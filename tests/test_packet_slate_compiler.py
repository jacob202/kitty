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


def test_companion_doc_matches_packet_standard_sections(tmp_path: Path):
    payload = _source()
    payload["packets"][0]["outcome"] = "Jacob can see the new behavior without reading implementation details."
    payload["packets"][0]["plan"] = [
        "Add a regression that proves the missing behavior.",
        "Implement the bounded change inside the declared fence.",
    ]
    payload["packets"][0]["not_in_scope"] = ["Do not change adjacent subsystems."]
    completed = _run_compiler(tmp_path, payload)

    assert completed.returncode == 0, completed.stderr
    doc = (tmp_path / "packets" / "DEMO-01.md").read_text(encoding="utf-8")
    assert "## What Jacob can do after this" in doc
    assert "Jacob can see the new behavior" in doc
    assert "## Why this is the next thing" in doc
    assert "## Plan" in doc
    assert "1. Add a regression" in doc
    assert "## Not in scope" in doc
    assert "- Do not change adjacent subsystems." in doc
    assert "**Tier 1 — mechanical.**" in doc
    assert "**Tier 2 — running app.**" in doc
    assert "**Tier 3 — product acceptance.**" in doc
    assert "## Stop condition" in doc
    assert "## Recovery" in doc


def test_interactive_doc_names_smoke_and_independent_acceptance(tmp_path: Path):
    payload = _source()
    entry = payload["packets"][0]
    entry["lane"] = "interactive"
    entry["outcome"] = "Jacob can complete the visible task from the running app."
    entry["tier2"] = "Run gateway/kitty-chat/tests/smoke/demo.spec.ts at desktop and iPhone-14 widths."
    entry["tier3"] = "An independent reviewer completes the task in the running app and records Product Acceptance."
    entry["manifest"]["validation_commands"] = [
        "cd gateway/kitty-chat && npx vitest run tests/Demo.test.tsx --reporter=dot",
        "cd gateway/kitty-chat && npx playwright test tests/smoke/demo.spec.ts",
    ]
    completed = _run_compiler(tmp_path, payload)

    assert completed.returncode == 0, completed.stderr
    doc = (tmp_path / "packets" / "DEMO-01.md").read_text(encoding="utf-8")
    assert "**Builder manifest:** none" in doc
    assert "**Tier 1 — mechanical.** Interactive validation" in doc
    assert "gateway/kitty-chat/tests/smoke/demo.spec.ts" in doc
    assert "independent reviewer" in doc.lower()


def test_interactive_hold_reason_marks_doc_held_without_entering_manifest(tmp_path: Path):
    payload = _source()
    entry = payload["packets"][0]
    entry["lane"] = "interactive"
    entry["hold_reason"] = "PR #999 owns the required frontend seam."
    entry["manifest"]["validation_commands"] = [
        "cd gateway/kitty-chat && npx vitest run tests/Demo.test.tsx --reporter=dot"
    ]
    completed = _run_compiler(tmp_path, payload)

    assert completed.returncode == 0, completed.stderr
    manifest = json.loads((tmp_path / "initiative.json").read_text(encoding="utf-8"))
    assert manifest["packets"] == []
    doc = (tmp_path / "packets" / "DEMO-01.md").read_text(encoding="utf-8")
    assert "**Owner:** interactive (held)" in doc
    assert "PR #999 owns the required frontend seam." in doc
