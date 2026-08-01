"""Black-box tests for the deterministic product-acceptance enforcement (#349).

Runs the real `.github/scripts/product_acceptance.py` CLI as a subprocess and
asserts the four scenarios the #349 task card demands:

1. an intentionally incomplete user-facing PR fails for missing receipt evidence;
2. a valid user-facing fixture passes;
3. a docs-only/backend-only fixture is not falsely blocked;
4. the reviewer-confirmed "not user-facing" override is honoured.

These tests are the non-vacuous proof: they exercise the exact script the GitHub
Action calls, not a copy of its logic.
"""

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / ".github" / "scripts" / "product_acceptance.py"

UI_PATH = "gateway/kitty-chat/src/components/SomeView.tsx"
BACKEND_PATH = "gateway/routes/images.py"
DOCS_PATH = "docs/WORKFLOW.md"


def run_cmd(cmd: list[str]) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), *cmd],
        capture_output=True,
        text=True,
        check=False,
    )
    result: dict = {"stderr": proc.stderr}
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT="):
            result = json.loads(line[len("RESULT="):])
    return proc.returncode, result


def write(tmp_path: Path, name: str, text: str) -> str:
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return str(p)


def receipt(evidence: str = "ordered screenshots + Playwright mobile run", reviewer: str = "ama-reviewer", completed: bool = False) -> str:
    completion = "- [x] A reviewer who did not implement the change completed the task in the running app." if completed else "- [ ] A reviewer who did not implement the change completed the task in the running app."
    return f"""## Summary
- fix the mobile shell

## Test plan
- [x] vitest 304/304, build green, playwright mobile 5/5

## Product acceptance
- User goal: use kitty on a phone
- Starting state and dependent services: gateway up, image engines offline
- Running-app steps and visible result: tapped through all six destinations
- Failure/recovery path tested: Studio offline shows check again
- Viewports tested: iPhone 14 Pro (393x852) + desktop 1280
- Evidence: {evidence}
- Independent task-completion reviewer: {reviewer}
- Remaining limitations or dead ends: none

- [x] Every visible primary control either completes its task or is disabled with one clear recovery action.
- [x] I tested required services both available and unavailable/misconfigured.
- [x] There is no horizontal page overflow, clipped dialog, obscured action, or off-screen primary navigation at the mobile viewport.
- [x] Errors explain what failed and what the user can do next; no raw server error is the primary message.
- [x] Normal user workflows do not require packet IDs, KTF phases, ports, env vars, YAML, MCP, LiteLLM, terminal commands, or Mac file paths.
{completion}
"""


def override_body(reason: str = "backend-only — gateway route, no UI touched") -> str:
    return f"""## Product acceptance (required for user-facing changes)
- User goal:
- Evidence:

### Not user-facing override
- [x] Not user-facing; the product-acceptance block above is not applicable.
- Reason (required when checked): {reason}
"""


def incomplete_body() -> str:
    # Every required field empty or template-placeholder.
    return """## Summary
- change something

## Test plan
- [x] checked

## Product acceptance
- User goal: <!-- what a person is trying to accomplish, in ordinary language -->
- Starting state and dependent services:
- Running-app steps and visible result:
- Failure/recovery path tested:
- Viewports tested:
- Evidence:
- Independent task-completion reviewer:
- Remaining limitations or dead ends:
"""


def paths_file(tmp_path: Path, name: str, *paths: str) -> str:
    # Unique file per call — a shared default file would let one fixture
    # overwrite another (the ORIGINAL bug that made this test pass-state flaky).
    p = tmp_path / f"paths-{name}.txt"
    p.write_text("\n".join(paths) + "\n", encoding="utf-8")
    return str(p)


def test_incomplete_user_facing_pr_fails_for_missing_receipt(tmp_path: Path) -> None:
    body = write(tmp_path, "incomplete.md", incomplete_body())
    pf = paths_file(tmp_path, "ui", UI_PATH)

    _, cls = run_cmd(["classify", "--paths-file", pf, "--body-file", body])
    assert cls["user_facing"] is True

    code, res = run_cmd(["validate", "--body-file", body])
    assert code == 1, "incomplete user-facing PR must fail the receipt validation"
    assert res["missing"], "every required field is empty in this fixture"
    assert set(res["missing"]) == {
        "User goal:",
        "Starting state and dependent services:",
        "Running-app steps and visible result:",
        "Failure/recovery path tested:",
        "Viewports tested:",
        "Evidence:",
        "Independent task-completion reviewer:",
        "Remaining limitations or dead ends:",
    }


def test_valid_user_facing_fixture_passes(tmp_path: Path) -> None:
    body = write(tmp_path, "valid.md", receipt())
    _, cls = run_cmd(["classify", "--paths-file", paths_file(tmp_path, "ui", UI_PATH), "--body-file", body])
    assert cls["user_facing"] is True

    code, res = run_cmd(["validate", "--body-file", body])
    assert code == 0, "fully-filled receipt must pass"
    assert res["pass"] is True
    assert res["missing"] == []


def test_docs_or_backend_only_pr_is_not_falsely_blocked(tmp_path: Path) -> None:
    for path in (DOCS_PATH, BACKEND_PATH):
        body = write(tmp_path, "docs.md", incomplete_body())  # content irrelevant
        _, cls = run_cmd(["classify", "--paths-file", paths_file(tmp_path, "path", path), "--body-file", body])
        assert cls["user_facing"] is False, f"{path} must not be classified user-facing"


def test_reviewed_not_user_facing_override_is_honored(tmp_path: Path) -> None:
    body = write(tmp_path, "override.md", override_body())
    pf = paths_file(tmp_path, "ui", UI_PATH)

    _, cls = run_cmd(["classify", "--paths-file", pf, "--body-file", body])
    assert cls["touches_ui"] is True
    assert cls["override_valid"] is True
    assert cls["user_facing"] is False, "reviewed override must take the PR out of the gate"

    # Reasoning override with no recorded reason must NOT be honoured (loop closed).
    no_reason = write(tmp_path, "override-noreason.md", override_body(reason="<!-- leave blank -->"))
    _, cls2 = run_cmd(["classify", "--paths-file", pf, "--body-file", no_reason])
    assert cls2["override_valid"] is False
    assert cls2["user_facing"] is True, "unreasoned override cannot escape the gate"


def test_gate_command_enforces_only_user_facing_incomplete_prs(tmp_path: Path) -> None:
    ui = paths_file(tmp_path, "ui", UI_PATH)
    backend = paths_file(tmp_path, "backend", BACKEND_PATH)

    incomplete = write(tmp_path, "gap.md", incomplete_body())
    valid = write(tmp_path, "vr.md", receipt())
    ov = write(tmp_path, "ov.md", override_body())
    out = str(tmp_path / "gate.json")

    # user-facing + incomplete receipt -> exit 1, should_review true
    code, doc = run_gate(incomplete, ui, out)
    assert code == 1
    assert doc["should_review"] is True
    assert doc["classification"]["user_facing"] is True

    # user-facing + complete receipt -> exit 0
    code, doc = run_gate(valid, ui, out)
    assert code == 0
    assert doc["should_review"] is True
    assert doc["validation"]["pass"] is True

    # backend-only -> not user-facing -> exit 0, must not force a review
    code, doc = run_gate(incomplete, backend, out)
    assert code == 0
    assert doc["should_review"] is False

    # UI paths but a valid, reviewed override -> exit 0, not enforced
    code, doc = run_gate(ov, ui, out)
    assert code == 0
    assert doc["should_review"] is False

    # --out produced a parseable RESULT file
    assert "RESULT=" in Path(out).read_text(encoding="utf-8")


def run_gate(body: str, paths: str, out: str) -> tuple[int, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "gate", "--paths-file", paths, "--body-file", body, "--out", out],
        capture_output=True,
        text=True,
        check=False,
    )
    result: dict = {"stderr": proc.stderr}
    for line in proc.stdout.splitlines():
        if line.startswith("RESULT="):
            result = json.loads(line[len("RESULT="):])
    return proc.returncode, result


def test_unit_test_only_evidence_produces_a_warning_not_a_false_block(tmp_path: Path) -> None:
    # Requirement: a unit-test result is not runtime task evidence. We surface
    # that as a warning; the structurally-complete receipt still passes so a
    # legitimate receipt is not falsely blocked.
    body = write(tmp_path, "weake.md", receipt(evidence="unit tests pass, component screenshot"))
    code, res = run_cmd(["validate", "--body-file", body])
    assert code == 0
    assert any("unit-test/component proof" in w for w in res["warnings"])
