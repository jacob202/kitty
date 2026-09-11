from __future__ import annotations

import hashlib
import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "evals" / "codex_review_fidelity"
DETECT_PATH = EVAL_ROOT / "detect.py"
SCORE_PATH = EVAL_ROOT / "score.py"
CORPUS_PATH = EVAL_ROOT / "corpus.json"

FULL_SHA_A = "0" * 40
FULL_SHA_B = "1" * 40


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_score_module():
    assert SCORE_PATH.exists(), "codex review-fidelity scorer must exist"
    return _load("codex_review_fidelity_score", SCORE_PATH)


def load_detect_module():
    assert DETECT_PATH.exists(), "codex review-fidelity detector must exist"
    return _load("codex_review_fidelity_detect", DETECT_PATH)


def _finding(path: str, line: int, severity: str = "P1", *, real: bool = False, start: int | None = None) -> dict:
    return {
        "path": path,
        "line": line,
        "severity": severity,
        "title": "t",
        "detail": "d",
        "hunk": {"new_start": start if start is not None else line - 2, "new_lines": 20, "context": 30},
        "confirmed_real": real,
    }


def _unit(pr: int, findings: list[dict]) -> dict:
    return {"pr": pr, "title": f"PR {pr}", "base": FULL_SHA_A, "head": FULL_SHA_B, "codex_findings": findings}


def _candidate(path: str, line: int | None, severity: str = "P1") -> dict:
    return {"path": path, "line": line, "severity": severity, "title": "t", "detail": "d"}


def _write(tmp_path: Path, units: list[dict], observations: dict) -> tuple[Path, Path]:
    corpus_path = tmp_path / "corpus.json"
    corpus_path.write_text(json.dumps({"version": 1, "review_units": units}), encoding="utf-8")
    obs_path = tmp_path / "observations.json"
    obs_path.write_text(json.dumps(observations), encoding="utf-8")
    return corpus_path, obs_path


def _observations(units: dict) -> dict:
    return {
        "corpus_version": 1,
        "provenance": {"model": "stub", "endpoint": "http://stub"},
        "review_units": units,
    }


# --- module presence and eval notes convention ---------------------------------


def test_eval_modules_exist() -> None:
    load_score_module()
    load_detect_module()


def test_eval_notes_are_txt_not_markdown() -> None:
    assert (EVAL_ROOT / "README.txt").exists()
    assert not (EVAL_ROOT / "README.md").exists()


# --- frozen corpus integrity ----------------------------------------------------


def test_frozen_corpus_is_internally_consistent() -> None:
    corpus = load_json(CORPUS_PATH)
    assert corpus["version"] == 1
    units = corpus["review_units"]
    findings = [f for u in units for f in u["codex_findings"]]
    assert len(units) == corpus["totals"]["review_units"]
    assert len(findings) == corpus["totals"]["findings"]
    assert sum(1 for f in findings if f["confirmed_real"]) == corpus["totals"]["confirmed_real"]
    assert sum(1 for f in findings if f["human_replied"]) == corpus["totals"]["human_replied"]
    # A confirmed fix is necessarily also a human-replied finding.
    assert corpus["totals"]["confirmed_real"] <= corpus["totals"]["human_replied"]
    assert {f["severity"] for f in findings} == {"P1", "P2"}
    assert len({f["id"] for f in findings}) == len(findings)
    assert all(f["path"] and f["title"] and f["detail"] for f in findings)


def test_frozen_corpus_units_are_reconstructable_and_unique() -> None:
    corpus = load_json(CORPUS_PATH)
    pairs = []
    for unit in corpus["review_units"]:
        assert len(unit["base"]) == 40 and len(unit["head"]) == 40
        pairs.append((unit["base"], unit["head"]))
        assert unit["codex_findings"], f"review unit {unit['pr']} carries no findings"
    assert len(set(pairs)) == len(pairs)


def test_frozen_corpus_locations_are_usable_for_matching() -> None:
    corpus = load_json(CORPUS_PATH)
    findings = [f for u in corpus["review_units"] for f in u["codex_findings"]]
    assert all(isinstance(f["line"], int) for f in findings)
    assert all(isinstance(f["hunk"]["new_start"], int) for f in findings)


# --- matching semantics ---------------------------------------------------------


def test_matching_requires_the_same_file() -> None:
    score = load_score_module()
    assert not score._matches(_candidate("a.py", 10), _finding("b.py", 10), 10)
    assert score._matches(_candidate("a.py", 10), _finding("a.py", 10), 10)


def test_matching_tolerates_small_line_drift_but_not_far_drift() -> None:
    score = load_score_module()
    finding = _finding("a.py", 100, start=90)
    assert score._matches(_candidate("a.py", 108), finding, 10)
    assert score._matches(_candidate("a.py", 92), finding, 10)
    assert not score._matches(_candidate("a.py", 140), finding, 10)


def test_candidate_without_a_line_cannot_match() -> None:
    score = load_score_module()
    assert not score._matches(_candidate("a.py", None), _finding("a.py", 10), 10)


# --- scoring reproducibility ----------------------------------------------------


def test_score_counts_recall_precision_and_confirmed_real(tmp_path) -> None:
    score = load_score_module()
    units = [
        _unit(1, [_finding("a.py", 10, real=True), _finding("a.py", 200), _finding("b.py", 5, "P2")]),
        _unit(2, [_finding("c.py", 7, real=True)]),
    ]
    observations = _observations(
        {
            "1": {"chunks": 1, "elapsed_seconds": 1.0, "chunk_errors": [],
                  "findings": [_candidate("a.py", 12), _candidate("zz.py", 1)]},
            "2": {"chunks": 1, "elapsed_seconds": 1.0, "chunk_errors": [], "findings": []},
        }
    )
    corpus_path, obs_path = _write(tmp_path, units, observations)
    metrics = score.score(corpus_path, obs_path)

    assert metrics["recall"]["codex_findings"] == 4
    assert metrics["recall"]["location_matched"] == 1
    assert metrics["recall"]["location_match_rate"] == pytest.approx(0.25)
    assert metrics["recall"]["p1"] == {"total": 3, "matched": 1, "rate": pytest.approx(1 / 3)}
    assert metrics["recall"]["p2"] == {"total": 1, "matched": 0, "rate": 0.0}
    assert metrics["recall"]["confirmed_real"] == {"total": 2, "matched": 1, "rate": 0.5}
    assert metrics["precision"] == {
        "candidate_findings": 2,
        "located_against_a_codex_finding": 1,
        "candidate_location_precision": 0.5,
    }
    assert len(metrics["missed_findings"]) == 3


def test_missed_findings_name_the_unreproduced_defects(tmp_path) -> None:
    score = load_score_module()
    units = [_unit(1, [_finding("a.py", 10, "P1", real=True), _finding("b.py", 5, "P2")])]
    observations = _observations({"1": {"chunks": 1, "findings": [_candidate("a.py", 10)], "chunk_errors": []}})
    corpus_path, obs_path = _write(tmp_path, units, observations)
    metrics = score.score(corpus_path, obs_path)

    assert metrics["missed_findings"] == [
        {"pr": 1, "path": "b.py", "line": 5, "severity": "P2", "title": "t", "confirmed_real": False}
    ]


def test_unrun_units_are_reported_rather_than_scored_as_misses(tmp_path) -> None:
    score = load_score_module()
    units = [_unit(1, [_finding("a.py", 10)]), _unit(2, [_finding("b.py", 10)])]
    observations = _observations({"1": {"chunks": 1, "findings": [_candidate("a.py", 10)], "chunk_errors": []}})
    corpus_path, obs_path = _write(tmp_path, units, observations)
    metrics = score.score(corpus_path, obs_path)

    assert metrics["provenance"]["review_units_run"] == 1
    assert metrics["provenance"]["review_units_not_run"] == 1
    assert {u["pr"]: u["status"] for u in metrics["per_unit"]} == {1: "run", 2: "not_run"}


def test_chunk_errors_are_surfaced_not_hidden(tmp_path) -> None:
    score = load_score_module()
    units = [_unit(1, [_finding("a.py", 10)])]
    observations = _observations(
        {"1": {"chunks": 2, "findings": [], "chunk_errors": ["chunk 2/2: HTTP 500"]}}
    )
    corpus_path, obs_path = _write(tmp_path, units, observations)
    metrics = score.score(corpus_path, obs_path)
    assert metrics["provenance"]["chunk_errors"] == 1


def test_version_mismatch_and_unknown_units_are_rejected(tmp_path) -> None:
    score = load_score_module()
    units = [_unit(1, [_finding("a.py", 10)])]

    corpus_path, obs_path = _write(tmp_path, units, {"corpus_version": 2, "review_units": {"1": {"findings": []}}})
    with pytest.raises(ValueError, match="version"):
        score.score(corpus_path, obs_path)

    corpus_path, obs_path = _write(tmp_path, units, _observations({"999": {"findings": []}}))
    with pytest.raises(ValueError, match="unknown review units"):
        score.score(corpus_path, obs_path)


# --- detector parsing and plumbing ----------------------------------------------


def test_parse_findings_handles_sentinel_prose_and_junk() -> None:
    detect = load_detect_module()
    assert detect.parse_findings("NO_ACTIONABLE_FINDINGS") == []
    parsed = detect.parse_findings(
        'Here you go:\n[{"path": "a.py", "line": 4, "severity": "p1", "title": "x", "detail": "y"}]\nDone.'
    )
    assert parsed == [{"path": "a.py", "line": 4, "severity": "P1", "title": "x", "detail": "y"}]
    # A genuinely empty array is a valid "no findings" answer.
    assert detect.parse_findings("[]") == []


def test_parse_findings_refuses_an_array_that_cannot_be_a_findings_list() -> None:
    detect = load_detect_module()
    # Regression: this must raise rather than report a confident zero. A reasoning model
    # that narrates before answering leaves incidental brackets in the prose, and quietly
    # accepting one turned a run that found defects into "0 findings, 0 errors".
    with pytest.raises(ValueError, match="not a findings list"):
        detect.parse_findings("I reviewed [1, 2] and found problems, but ran out of room.")
    with pytest.raises(ValueError, match="not a findings list"):
        detect.parse_findings('[{"line": 4, "severity": "P1"}]')


def test_parse_findings_rejects_a_response_with_neither_array_nor_sentinel() -> None:
    detect = load_detect_module()
    with pytest.raises(ValueError):
        detect.parse_findings("I could not review this.")


def test_parse_findings_reads_the_answer_after_reasoning_prose() -> None:
    detect = load_detect_module()
    reasoned = (
        "Let us consider the diff. The changed file [a.py] adds a check.\n"
        "We must not report speculation, so [maybe] skip it.\n"
        'Final answer:\n[{"path": "a.py", "line": 9, "severity": "P2", "title": "t", "detail": "d"}]\n'
    )
    assert detect.parse_findings(reasoned) == [
        {"path": "a.py", "line": 9, "severity": "P2", "title": "t", "detail": "d"}
    ]


def test_parse_findings_does_not_treat_an_echoed_sentinel_as_the_answer() -> None:
    detect = load_detect_module()
    # A reasoning model often restates the instruction before answering. The array wins.
    echoed = (
        "The instructions say to reply NO_ACTIONABLE_FINDINGS when nothing is found.\n"
        'However I found one:\n[{"path": "b.py", "line": 3, "severity": "P1", "title": "t", "detail": "d"}]\n'
    )
    assert detect.parse_findings(echoed) == [
        {"path": "b.py", "line": 3, "severity": "P1", "title": "t", "detail": "d"}
    ]


def test_parse_findings_ignores_a_truncated_array_from_a_budget_starved_model() -> None:
    detect = load_detect_module()
    # Exactly the failure that produced silent zero-finding runs before max_tokens was raised.
    truncated = 'We are given a diff chunk.\n[{"path": "a.py", "line": 4, "sev'
    with pytest.raises(ValueError, match="neither a JSON array"):
        detect.parse_findings(truncated)


def test_review_unit_diff_requires_full_shas() -> None:
    detect = load_detect_module()
    with pytest.raises(ValueError):
        detect.review_unit_diff("deadbeef", FULL_SHA_B)


def test_ensure_revision_is_a_noop_when_git_already_has_the_commit(monkeypatch) -> None:
    detect = load_detect_module()
    monkeypatch.setattr(detect, "_present", lambda revision: True)
    fetched: list[tuple] = []

    def fake_git(*args):
        fetched.append(args)
        return ""

    monkeypatch.setattr(detect, "_git", fake_git)
    assert detect.ensure_revision(FULL_SHA_B, pr=674) is False
    assert fetched == []


def test_ensure_revision_fetches_the_pr_ref_when_the_head_is_unreachable(monkeypatch) -> None:
    detect = load_detect_module()
    state = {"present": False}
    monkeypatch.setattr(detect, "_present", lambda revision: state["present"])
    fetched: list[tuple] = []

    def fake_git(*args):
        fetched.append(args)
        if args[0] == "fetch":
            state["present"] = True
        return ""

    monkeypatch.setattr(detect, "_git", fake_git)
    assert detect.ensure_revision(FULL_SHA_B, pr=674) is True
    assert fetched == [("fetch", "--quiet", "origin", "refs/pull/674/head")]


def test_ensure_revision_raises_when_the_ref_does_not_supply_the_commit(monkeypatch) -> None:
    detect = load_detect_module()
    monkeypatch.setattr(detect, "_present", lambda revision: False)
    monkeypatch.setattr(detect, "_git", lambda *args: "")
    with pytest.raises(RuntimeError, match="cannot be reproduced"):
        detect.ensure_revision(FULL_SHA_B, pr=674)


def test_detect_unit_records_findings_and_the_diff_hash(monkeypatch) -> None:
    detect = load_detect_module()
    unit = {"pr": 7, "title": "stub", "base": FULL_SHA_A, "head": FULL_SHA_B}
    diff = "diff --git a/x b/x\n+hello\n"
    monkeypatch.setattr(detect, "review_unit_diff", lambda base, head, **kwargs: diff)
    monkeypatch.setattr(
        detect, "_chat", lambda *a, **k: '[{"path": "x", "line": 1, "severity": "P1", "title": "t", "detail": "d"}]'
    )
    result = detect.detect_unit(unit, endpoint="http://stub", model="m", api_key=None, timeout=1.0)
    assert result["pr"] == 7
    assert result["chunks"] == 1
    assert result["chunk_errors"] == []
    assert result["findings"][0]["path"] == "x"
    assert result["diff_sha256"] == hashlib.sha256(diff.encode("utf-8")).hexdigest()


def test_detect_unit_records_a_chunk_failure_instead_of_dropping_it(monkeypatch) -> None:
    detect = load_detect_module()
    unit = {"pr": 8, "title": "stub", "base": FULL_SHA_A, "head": FULL_SHA_B}
    monkeypatch.setattr(detect, "review_unit_diff", lambda base, head, **kwargs: "diff --git a/x b/x\n+hello\n")

    def boom(*args, **kwargs):
        raise detect.EndpointError("HTTP 500 from stub")

    monkeypatch.setattr(detect, "_chat", boom)
    result = detect.detect_unit(unit, endpoint="http://stub", model="m", api_key=None, timeout=1.0)
    assert result["findings"] == []
    assert len(result["chunk_errors"]) == 1
    assert "HTTP 500" in result["chunk_errors"][0]


# --- endpoint behavior ----------------------------------------------------------


def _serve(handler_cls) -> tuple[HTTPServer, str]:
    server = HTTPServer(("127.0.0.1", 0), handler_cls)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_chat_round_trips_a_completion() -> None:
    detect = load_detect_module()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers["Content-Length"])
            payload = json.loads(self.rfile.read(length))
            assert payload["temperature"] == 0
            assert payload["messages"][0]["role"] == "system"
            body = json.dumps({"choices": [{"message": {"content": '{"ok": true}'}}]}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, endpoint = _serve(Handler)
    try:
        assert detect._chat(endpoint, "stub-model", None, "prompt", 5.0) == '{"ok": true}'
    finally:
        server.shutdown()
        server.server_close()


def test_chat_surfaces_endpoint_errors_loudly() -> None:
    detect = load_detect_module()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            body = b'{"error":"boom"}'
            self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server, endpoint = _serve(Handler)
    try:
        with pytest.raises(detect.EndpointError, match="HTTP 500"):
            detect._chat(endpoint, "stub-model", None, "prompt", 5.0)
    finally:
        server.shutdown()
        server.server_close()
