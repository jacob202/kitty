from src.builder.worker_health import check_worker_health


def test_check_worker_health_reports_missing_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: None)
    result = check_worker_health("not-real-cli")
    assert result.name == "not-real-cli"
    assert result.available is False
    assert "missing" in result.reason.lower()


def test_check_worker_health_reports_available_binary(monkeypatch):
    monkeypatch.setattr("shutil.which", lambda name: f"/usr/bin/{name}")
    result = check_worker_health("python")
    assert result.available is True
    assert result.path == "/usr/bin/python"

