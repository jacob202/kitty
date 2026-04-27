import scripts.eval_loop as eval_loop


def test_append_log_matches_four_column_iteration_table(tmp_path, monkeypatch):
    log_path = tmp_path / "iteration_log.md"
    monkeypatch.setattr(eval_loop, "ITERATION_LOG", log_path)

    eval_loop.append_log(1, "100.00%", "PASS", change="verification run")

    content = log_path.read_text()
    assert "| Attempt | Change | Eval Score | Status |" in content
    assert "| 1 | verification run | 100.00% | PASS |" in content
