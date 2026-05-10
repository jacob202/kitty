"""
Tests for chat log consolidation pipeline.
"""
import sys, os, pytest, tempfile, json
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from scripts.consolidate_chat_logs import _scan_logs, _extract_categories, dry_run, write_reviewed, run


class TestScanLogs:
    def test_scan_empty_dir(self, tmp_path):
        logs = _scan_logs(str(tmp_path))
        assert logs == []

    def test_scan_with_json(self, tmp_path):
        (tmp_path / "chat1.json").write_text('{"msg": "hello"}')
        (tmp_path / "chat2.json").write_text('{"msg": "world"}')
        logs = _scan_logs(str(tmp_path))
        assert len(logs) == 2

    def test_scan_with_md(self, tmp_path):
        (tmp_path / "notes.md").write_text("# Notes\n")
        logs = _scan_logs(str(tmp_path))
        assert len(logs) == 1


class TestExtractCategories:
    def test_empty_content(self):
        cats = _extract_categories("")
        assert all(len(v) == 0 for v in cats.values())

    def test_decision_extraction(self):
        content = "I decided to use MLX. This is a decision."
        cats = _extract_categories(content)
        assert len(cats["decisions"]) > 0

    def test_parked_feature(self):
        content = "Let's park this feature for later. It's parked."
        cats = _extract_categories(content)
        assert len(cats["parked_features"]) > 0

    def test_task_extraction(self):
        content = "TODO: build the brief. Task: write tests."
        cats = _extract_categories(content)
        assert len(cats["active_tasks"]) > 0

    def test_correction_extraction(self):
        content = "Correction: fix the indentation. That was wrong."
        cats = _extract_categories(content)
        assert len(cats["corrections"]) > 0

    def test_user_preference(self):
        content = "I prefer dark mode. User likes Python."
        cats = _extract_categories(content)
        assert len(cats["user_preferences"]) > 0

    def test_all_categories_present(self):
        cats = _extract_categories("test")
        expected = ["decisions", "parked_features", "active_tasks", "rejected_ideas",
                    "corrections", "user_preferences", "project_facts", "file_references",
                    "cleanup_candidates", "specialist_kb_candidates", "skill_candidates",
                    "bugs_failures", "open_loops"]
        for k in expected:
            assert k in cats, f"Missing category: {k}"


class TestDryRun:
    def test_dry_run_no_logs(self, tmp_path):
        result = dry_run(str(tmp_path))
        assert result["logs_found"] == 0
        assert result["logs_processed"] == 0

    def test_dry_run_with_logs(self, tmp_path):
        (tmp_path / "chat1.json").write_text(
            json.dumps({"messages": [{"role": "user", "content": "Decision: use MLX"}]})
        )
        result = dry_run(str(tmp_path))
        assert result["logs_found"] == 1
        assert result["logs_processed"] == 1
        assert "decisions" in result["categories"]

    def test_dry_run_returns_samples(self, tmp_path):
        (tmp_path / "chat1.json").write_text('{"msg": "Park this feature. Decision: go local."}')
        result = dry_run(str(tmp_path))
        assert "samples" in result
        samples = result["samples"]
        has_samples = any(len(v) > 0 for v in samples.values())
        assert has_samples, f"No samples found. Samples: {samples}"


class TestWriteReviewed:
    def test_write_report(self, tmp_path):
        result = {
            "logs_processed": 5,
            "categories": {"decisions": 2, "parked_features": 1},
            "samples": {"decisions": ["Decision: use MLX"], "parked_features": ["Park this"]},
            "errors": [],
        }
        output = tmp_path / "report.md"
        path = write_reviewed(result, str(output))
        assert os.path.exists(path)
        content = Path(path).read_text()
        assert "Chat Log Consolidation Report" in content
        assert "5" in content  # logs processed

    def test_write_with_errors(self, tmp_path):
        result = {
            "logs_processed": 1,
            "categories": {},
            "samples": {},
            "errors": ["chat1.json: decode error"],
        }
        output = tmp_path / "report_with_errors.md"
        path = write_reviewed(result, str(output))
        content = Path(path).read_text()
        assert "Errors" in content


class TestCli:
    def test_dry_run_prints_counts_and_writes_nothing(self, tmp_path, capsys):
        input_dir = tmp_path / "logs"
        input_dir.mkdir()
        (input_dir / "chat1.json").write_text('{"msg": "Decision: keep raw logs"}')

        code = run(["--project", str(tmp_path), "--input", "logs", "--dry-run"])

        output = capsys.readouterr().out
        assert code == 0
        assert "Chat log consolidation dry-run" in output
        assert "Logs found: 1" in output
        assert "decisions:" in output
        assert "Wrote report: no" in output
        assert not (tmp_path / "CHAT_LOG_CONSOLIDATION_REPORT.md").exists()

    def test_default_mode_is_dry_run(self, tmp_path, capsys):
        input_dir = tmp_path / "logs"
        input_dir.mkdir()
        (input_dir / "chat1.md").write_text("TODO: review this later")

        code = run(["--project", str(tmp_path), "--input", "logs"])

        output = capsys.readouterr().out
        assert code == 0
        assert "Chat log consolidation dry-run" in output
        assert "Wrote report: no" in output

    def test_write_reviewed_requires_output(self, tmp_path):
        with pytest.raises(SystemExit):
            run(["--project", str(tmp_path), "--input", str(tmp_path), "--write-reviewed"])

    def test_rejects_dry_run_and_write_reviewed_together(self, tmp_path):
        with pytest.raises(SystemExit):
            run([
                "--project", str(tmp_path),
                "--input", str(tmp_path),
                "--dry-run",
                "--write-reviewed",
                "--output", "report.md",
            ])

    def test_write_reviewed_writes_report(self, tmp_path, capsys):
        input_dir = tmp_path / "logs"
        input_dir.mkdir()
        (input_dir / "chat1.json").write_text('{"msg": "Park this feature for later"}')

        code = run([
            "--project", str(tmp_path),
            "--input", "logs",
            "--write-reviewed",
            "--output", "docs/report.md",
        ])

        output = capsys.readouterr().out
        report = tmp_path / "docs" / "report.md"
        assert code == 0
        assert report.exists()
        assert "Chat Log Consolidation Report" in report.read_text()
        assert "Wrote report:" in output
