"""The two PR gates that waive Dependabot must waive it the same way.

`pr-risk-guardrails.yml` gained a Dependabot waiver in #327 and
`pr-description-check.yml` did not, so the description gate pinned every
dependency PR red for a week. Nobody saw it because the gates were only ever
measured against human PRs. These tests pin the invariant the drift broke:
both gates waive exactly `dependabot[bot]`, and neither waives bots by suffix.
"""

from pathlib import Path

import pytest
import yaml

WORKFLOWS = Path(__file__).parent.parent / ".github/workflows"

GATES = {
    "pr-description-check.yml": "check-description",
    "pr-risk-guardrails.yml": "risk-guardrails",
}


def gate_script(filename: str, job_name: str) -> str:
    workflow = yaml.safe_load((WORKFLOWS / filename).read_text(encoding="utf-8"))
    for step in workflow["jobs"][job_name]["steps"]:
        script = (step.get("with") or {}).get("script")
        if script:
            return script
    raise AssertionError(f"no github-script step found in {filename}:{job_name}")


@pytest.mark.parametrize(("filename", "job_name"), sorted(GATES.items()))
def test_gate_waives_dependabot_by_exact_login(filename: str, job_name: str) -> None:
    script = gate_script(filename, job_name)
    assert '=== "dependabot[bot]"' in script, (
        f"{filename} must waive Dependabot by exact login; without it the gate "
        "pins every dependency PR red"
    )


def code_only(script: str) -> str:
    """Drop `//` comment lines.

    Both gates *name* the rejected `endsWith` approach in the comment that
    explains why they don't use it, so a naive substring check matches the
    prose it is meant to protect.
    """
    return "\n".join(
        line for line in script.splitlines() if not line.lstrip().startswith("//")
    )


@pytest.mark.parametrize(("filename", "job_name"), sorted(GATES.items()))
def test_gate_does_not_waive_bots_by_suffix(filename: str, job_name: str) -> None:
    script = code_only(gate_script(filename, job_name))
    assert 'endsWith("[bot]")' not in script, (
        f"{filename} must not waive every bot by suffix — Copilot and any "
        "future app open PRs carrying real code and workflow changes"
    )
