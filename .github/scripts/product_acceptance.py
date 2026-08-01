#!/usr/bin/env python3
"""Deterministic product-acceptance enforcement for issue #349.

Two distinct responsibilities, both free of API access so the GitHub Action can
run them on a bare runner:

- ``classify``  — is a PR user-facing? Rule is path-based and exact:
  any changed file under ``gateway/kitty-chat/`` is user-facing. An explicit,
  reason-bearing "Not user-facing override" from the PR template is the only
  escape, and the template makes it a reviewer-confirmed override, never a
  self-declaration. No LLM ever decides this.
- ``validate``  — for a user-facing PR, is the product task receipt present and
  non-placeholder on every required field? Unit-test results and component
  screenshots are not runtime task evidence; that surfaces as a warning here.

Exit codes: 0 = pass/waived, 1 = hard failure (missing required receipt fields).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

# Any change under the chat UI is treated as user-facing (#349 requirement 1).
USER_FACING_PREFIXES = ("gateway/kitty-chat/",)

RECEIPT_FIELDS = (
    "User goal:",
    "Starting state and dependent services:",
    "Running-app steps and visible result:",
    "Failure/recovery path tested:",
    "Viewports tested:",
    "Evidence:",
    "Independent task-completion reviewer:",
    "Remaining limitations or dead ends:",
)

# The self-check that a human actually completed the task in the running app.
COMPLETION_CHECK_RE = re.compile(
    r"-\s*\[([xX])\]\s*A reviewer who did not implement the change completed the task in the running app\.",
)

_OVERRIDE_RE = re.compile(
    r"-\s*\[([xX])\]"
    r"\s*Not user-facing; the product-acceptance block above is not applicable\.?",
)
_REASON_RE = re.compile(r"-\s*Reason \(required when checked\):\s*(.*)", re.IGNORECASE)
_PLACEHOLDER_RE = re.compile(r"<!--.*?-->", re.DOTALL)

# Evidence is "unit-test-ish only" if it cites test/component results but never
# mentions a running-app artifact. Advisory warning, not a hard failure, so a
# legitimate text-only receipt cannot be falsely blocked. Note "screen" is
# deliberately absent — "component screenshot" contains it and would otherwise
# never warn.
_UNIT_TESTY = re.compile(r"unit test|component scre|component preview|mock", re.IGNORECASE)
_RUNTIMEY = re.compile(
    r"record|playwright|browser|running|\.png|\.mp4|\.mov", re.IGNORECASE
)


def _strip_placeholders(text: str) -> str:
    return _PLACEHOLDER_RE.sub("", text).strip()


def _read(path: str | None) -> str:
    if path is None:
        return os.environ.get("PR_BODY", "")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def classify(changed_paths: list[str], body: str) -> dict[str, Any]:
    touches_ui = any(p.startswith(USER_FACING_PREFIXES) for p in changed_paths)

    m = _OVERRIDE_RE.search(body)
    override_checked = m is not None
    reason_match = _REASON_RE.search(body)
    reason = reason_match.group(1).strip() if reason_match else ""
    reason_provided = bool(reason) and "<!--" not in reason

    # The override only counts when the checkbox is checked AND a non-placeholder
    # reason names the change class (template contract).
    override_valid = override_checked and reason_provided

    return {
        "user_facing": touches_ui and not override_valid,
        "touches_ui": touches_ui,
        "override_checked": override_checked,
        "override_reason": reason if reason_provided else None,
        "override_valid": override_valid,
    }


def _field_value(body: str, label: str) -> str:
    # [ \t]* — NOT \s* — so the match cannot cross a line break and swallow the
    # next receipt field.
    m = re.search(r"-\s*" + re.escape(label) + r"[ \t]*(.*)", body, re.MULTILINE)
    if not m:
        return ""
    return _strip_placeholders(m.group(1))


def validate(body: str) -> dict[str, Any]:
    fields: dict[str, str] = {}
    missing: list[str] = []
    for label in RECEIPT_FIELDS:
        key = label.rstrip(":")
        value = _field_value(body, label)
        fields[key] = value
        if not value:
            missing.append(label)

    warnings: list[str] = []
    evidence = fields.get("Evidence", "")
    if evidence and _UNIT_TESTY.search(evidence) and not _RUNTIMEY.search(evidence):
        warnings.append(
            "Evidence field looks like unit-test/component proof, not running-app "
            "evidence. Add an ordered screenshot, short recording, or Playwright run."
        )

    if RECEIPT_FIELDS[0] in missing:
        warnings.append("Receipt fields are missing entirely; did the Product acceptance section get filled in?")

    completion_checked = COMPLETION_CHECK_RE.search(body) is not None
    if completion_checked:
        warnings.append("The 'independent reviewer completed the task' self-check is ticked, but self-attestation is not evidence — paste the reviewer's finding or leave it for the reviewer to confirm.")

    return {
        "fields": fields,
        "missing": missing,
        "warnings": warnings,
        "pass": not missing,
    }


def gate(args: argparse.Namespace) -> int:
    """Combined classification + receipt validation used by the GitHub Action.

    Emits one JSON document (to ``--out`` and to stdout, prefixed with RESULT=)
    carrying the classification, the validation detail and the enforcement
    decision. Exit code 1 iff the PR is user-facing (no valid override) and the
    receipt is missing required fields — i.e. fail loud, never silently pass.
    """
    body = _read(args.body_file)
    paths: list[str] = []
    if args.paths_file and os.path.exists(args.paths_file):
        with open(args.paths_file, encoding="utf-8") as fh:
            paths = [ln.strip() for ln in fh if ln.strip()]

    cls = classify(paths, body)
    val = validate(body)
    should_review = bool(cls["user_facing"])
    exit_code = 1 if (cls["user_facing"] and bool(val["missing"])) else 0

    doc = {
        "classification": cls,
        "validation": val,
        "should_review": should_review,
        "exit_code": exit_code,
    }
    line = "RESULT=" + json.dumps(doc, sort_keys=True)
    print(line)
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            fh.write(line + "\n")
    return exit_code


def _parse_args() -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("classify", help="Emit user-facing + override classification")
    c.add_argument("--paths-file", help="file with one changed path per line")
    c.add_argument("--body-file", help="file with the PR body")
    c.set_defaults(handler=lambda ns: _emit(ns, "classify"))

    v = sub.add_parser("validate", help="Validate the product task receipt")
    v.add_argument("--body-file", help="file with the PR body")
    v.set_defaults(handler=lambda ns: _emit(ns, "validate"))

    g = sub.add_parser("gate", help="Combined classify+validate for the workflow")
    g.add_argument("--paths-file", help="file with one changed path per line")
    g.add_argument("--body-file", help="file with the PR body")
    g.add_argument("--out", help="write the RESULT JSON to this file")
    g.set_defaults(handler=gate)

    return ap.parse_args()


def _emit(ns: argparse.Namespace, which: str) -> int:
    body = _read(ns.body_file)
    if which == "classify":
        paths = []
        if ns.paths_file and os.path.exists(ns.paths_file):
            with open(ns.paths_file, encoding="utf-8") as fh:
                paths = [ln.strip() for ln in fh if ln.strip()]
        result = classify(paths, body)
        print("RESULT=" + json.dumps(result, sort_keys=True))
        return 0
    result = validate(body)
    print("RESULT=" + json.dumps(result, sort_keys=True))
    return 1 if result["missing"] else 0


def main() -> int:
    ns = _parse_args()
    return ns.handler(ns)


if __name__ == "__main__":
    sys.exit(main())
