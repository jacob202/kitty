from __future__ import annotations

def test_gateway_secret_warning_matches_fail_closed_auth(monkeypatch, tmp_path) -> None:
    from gateway import doctor

    monkeypatch.setattr(doctor, "ROOT", tmp_path)
    (tmp_path / ".env").write_text("OPENROUTER_API_KEY=set\n", encoding="utf-8")

    checks = doctor._check_env({"OPENROUTER_API_KEY": "set"})

    gateway_secret = next(c for c in checks if c.name == "env:gateway_secret")

    assert gateway_secret.level == "WARN"
    assert "fails closed" in gateway_secret.detail
    assert "accepts any request" not in gateway_secret.detail


def test_doctor_uses_litellm_readiness_endpoint(monkeypatch) -> None:
    from gateway import doctor

    seen_urls: list[str] = []

    def fake_http_ok(url: str, timeout: float = 3.0, headers: dict | None = None) -> bool:
        seen_urls.append(url)
        return True

    monkeypatch.setattr(doctor, "_http_ok", fake_http_ok)

    doctor._check_services({"GATEWAY_PORT": "5001", "LITELLM_PORT": "8001"})

    assert "http://127.0.0.1:8001/health/readiness" in seen_urls
