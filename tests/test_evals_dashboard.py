import json

from src.observability.evals_dashboard import load_eval_dashboard


def write_artifact(root, name, run_id, rate, passed=5, total=5, checks=None):
    path = root / name
    path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "suite": "smoke",
                "started_at": 100.0,
                "scores": {"smoke": {"passed": passed, "total": total, "rate": rate}},
                "checks": checks if checks is not None else [{"name": "ok", "passed": True, "reason": ""}],
            }
        ),
        encoding="utf-8",
    )
    return path


def test_missing_artifact_dir_returns_empty_summary(tmp_path):
    dashboard = load_eval_dashboard(tmp_path / "missing")

    assert dashboard["artifact_count"] == 0
    assert dashboard["latest"] is None
    assert dashboard["trend"]["direction"] == "unknown"


def test_latest_artifact_is_selected_by_mtime(tmp_path):
    older = write_artifact(tmp_path, "old_smoke.json", "old", 0.8, passed=4)
    newer = write_artifact(tmp_path, "new_smoke.json", "new", 1.0)
    older.touch()
    newer.touch()

    dashboard = load_eval_dashboard(tmp_path)

    assert dashboard["artifact_count"] == 2
    assert dashboard["latest"]["run_id"] == "new"
    assert dashboard["latest"]["score"]["rate"] == 1.0


def test_failed_checks_are_surfaced(tmp_path):
    write_artifact(
        tmp_path,
        "fail_smoke.json",
        "fail",
        0.5,
        passed=1,
        total=2,
        checks=[
            {"name": "ok", "passed": True, "reason": ""},
            {"name": "chat_not_500", "passed": False, "reason": "got 500"},
        ],
    )

    dashboard = load_eval_dashboard(tmp_path)

    assert dashboard["latest"]["failed_checks"] == [{"name": "chat_not_500", "reason": "got 500"}]


def test_corrupt_artifacts_are_counted_not_raised(tmp_path):
    write_artifact(tmp_path, "good_smoke.json", "good", 1.0)
    (tmp_path / "bad_smoke.json").write_text("{not json", encoding="utf-8")

    dashboard = load_eval_dashboard(tmp_path)

    assert dashboard["artifact_count"] == 2
    assert dashboard["parsed_count"] == 1
    assert dashboard["corrupt_count"] == 1


def test_trend_compares_latest_to_previous(tmp_path):
    first = write_artifact(tmp_path, "first_smoke.json", "first", 1.0)
    second = write_artifact(tmp_path, "second_smoke.json", "second", 0.8)
    first.touch()
    second.touch()

    dashboard = load_eval_dashboard(tmp_path)

    assert dashboard["latest"]["run_id"] == "second"
    assert dashboard["trend"]["direction"] == "down"
    assert dashboard["trend"]["delta"] == -0.19999999999999996
    assert dashboard["trend"]["previous_run_id"] == "first"
