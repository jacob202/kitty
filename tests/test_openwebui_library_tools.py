from kitty_gateway.openwebui_library_tools.kitty_knowledge_search import Tools as KnowledgeTools
from kitty_gateway.openwebui_library_tools.kitty_memory_search import Tools as MemoryTools


def test_knowledge_search_hits_gateway_search_route(monkeypatch):
    seen = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"knowledge": [{"source": "kb.md", "text": "facts"}]}

    def fake_get(url, params=None, timeout=None):
        seen["url"] = url
        seen["params"] = params
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    tool = KnowledgeTools()
    result = tool.search_knowledge("honda wiring")

    assert seen["url"] == "http://127.0.0.1:8000/search"
    assert seen["params"] == {"q": "honda wiring", "limit": 5}
    assert "kb.md" in result


def test_memory_search_hits_gateway_search_route(monkeypatch):
    seen = {}

    class FakeResponse:
        status_code = 200

        def json(self):
            return {"memories": [{"source": "memory", "text": "remember this"}]}

    def fake_get(url, params=None, timeout=None):
        seen["url"] = url
        seen["params"] = params
        seen["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("requests.get", fake_get)

    tool = MemoryTools()
    result = tool.search_memory("remember this")

    assert seen["url"] == "http://127.0.0.1:8000/search"
    assert seen["params"] == {"q": "remember this", "limit": 5}
    assert "remember this" in result

