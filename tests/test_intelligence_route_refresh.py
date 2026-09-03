from gateway.routes import intelligence


def test_refresh_connections_requests_magic_in_visible_response(monkeypatch):
    monkeypatch.setattr(intelligence.magic_kitty, 'discover_connections', lambda force=False: [{'title': 'x'}])
    calls = []
    monkeypatch.setattr(intelligence.intelligence_projection, 'build_projection', lambda **kwargs: calls.append(kwargs) or {'items': []})
    assert intelligence.refresh_connections() == {'items': []}
    assert calls == [{'limit': 3, 'ensure_source': 'magic'}]
