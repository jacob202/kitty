from gateway.search_client import OpenWebUISearchClient


def test_search_client_reauths_after_cold_start(monkeypatch):
    client = OpenWebUISearchClient.__new__(OpenWebUISearchClient)
    client.url = "http://127.0.0.1:3001"
    client.token = None
    client.kb_map = {}

    seen = {"logins": 0, "kb_map": 0, "headers": []}

    def fake_login():
        seen["logins"] += 1
        return "fresh-token"

    def fake_get_kb_map():
        seen["kb_map"] += 1
        return {"electronics": "kb-123"}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "content": "MOSFET failure notes",
                        "metadata": {"source": "electronics.pdf"},
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["headers"].append(headers)
        assert url == "http://127.0.0.1:3001/api/v1/retrieval/query/collection"
        assert json == {
            "collection_names": ["kb-123"],
            "query": "fix blown mosfet",
            "k": 5,
        }
        assert timeout == 60
        return FakeResponse()

    client._login = fake_login
    client._get_kb_map = fake_get_kb_map
    monkeypatch.setattr("gateway.search_client.get_collection_id", lambda name: "kb-123")
    monkeypatch.setattr("requests.post", fake_post)

    result = client.search_kb("electronics", "fix blown mosfet")

    assert result["summary"] == "[Source: electronics.pdf]\nMOSFET failure notes"
    assert result["hit_count"] == 1
    assert result["sources"] == ["electronics.pdf"]
    assert result["kb_name"] == "electronics"
    assert result["kb_id"] == "kb-123"
    assert client.token == "fresh-token"
    assert client.kb_map == {"electronics": "kb-123"}
    assert seen["logins"] == 1
    assert seen["kb_map"] == 1
    assert seen["headers"] == [{"Authorization": "Bearer fresh-token", "Content-Type": "application/json"}]


def test_search_client_returns_empty_diagnostics(monkeypatch):
    client = OpenWebUISearchClient.__new__(OpenWebUISearchClient)
    client.url = "http://127.0.0.1:3001"
    client.token = "fresh-token"
    client.kb_map = {"electronics": "kb-123"}
    monkeypatch.setattr("gateway.search_client.get_collection_id", lambda name: "kb-123")

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {"results": []}

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: FakeResponse())

    result = client.search_kb("electronics", "fix blown mosfet")

    assert result["summary"] == "No relevant context found."
    assert result["hit_count"] == 0
    assert result["sources"] == []
    assert result["status"] == "ok"


def test_search_client_parses_retrieval_matrix_shape(monkeypatch):
    client = OpenWebUISearchClient.__new__(OpenWebUISearchClient)
    client.url = "http://127.0.0.1:3001"
    client.token = "fresh-token"
    client.kb_map = {"electronics": "kb-123"}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "documents": [["first hit", "second hit"]],
                "metadatas": [[
                    {"source": "one.pdf"},
                    {"source": "two.pdf"},
                ]],
                "distances": [[0.1, 0.2]],
            }

    monkeypatch.setattr("requests.post", lambda *args, **kwargs: FakeResponse())

    result = client.search_kb("electronics", "Sansui MOSFET")

    assert result["hit_count"] == 2
    assert result["sources"] == ["one.pdf", "two.pdf"]
    assert "first hit" in result["summary"]
    assert "second hit" in result["summary"]


def test_search_client_uses_hyde_query(monkeypatch):
    client = OpenWebUISearchClient.__new__(OpenWebUISearchClient)
    client.url = "http://127.0.0.1:3001"
    client.token = "fresh-token"
    client.kb_map = {}

    seen = {"queries": []}

    class FakeResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "results": [
                    {
                        "content": "Likely failed gate resistor on the MOSFET stage.",
                        "metadata": {"source": "hyde-hit.pdf"},
                    }
                ]
            }

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["queries"].append(json["query"])
        return FakeResponse()

    monkeypatch.setattr("gateway.search_client.get_collection_id", lambda name: "kb-123")
    monkeypatch.setattr("gateway.search_client.call_llm", lambda **kwargs: "Likely failed gate resistor on the MOSFET stage.")
    monkeypatch.setattr("requests.post", fake_post)

    result = client.search_kb("electronics", "why did the sansui mosfet fail", use_hyde=True)

    assert seen["queries"] == ["Likely failed gate resistor on the MOSFET stage."]
    assert result["method_used"] == "hyde+vector"


def test_search_client_falls_back_to_keyword_search(monkeypatch):
    client = OpenWebUISearchClient.__new__(OpenWebUISearchClient)
    client.url = "http://127.0.0.1:3001"
    client.token = "fresh-token"
    client.kb_map = {}

    class VectorResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return {
                "documents": [["generic text"]],
                "metadatas": [[{"source": "generic.pdf", "chunk_id": "vec-1"}]],
                "distances": [[0.92]],
            }

    file_payload = {
        "items": [
            {
                "id": "file-1",
                "filename": "Sansui AU-7900 service notes.txt",
                "data": {"content": "The AU-7900 uses 2SC1845 parts on the driver board."},
                "meta": {"name": "Sansui AU-7900 service notes.txt"},
            }
        ]
    }

    def fake_post(*args, **kwargs):
        return VectorResponse()

    class FilesResponse:
        status_code = 200

        def raise_for_status(self):
            return None

        def json(self):
            return file_payload

    monkeypatch.setattr("gateway.search_client.get_collection_id", lambda name: "kb-123")
    monkeypatch.setattr("requests.post", fake_post)
    monkeypatch.setattr("requests.get", lambda *args, **kwargs: FilesResponse())

    result = client.search_kb("electronics", "Need AU-7900 2SC1845 driver info")

    assert result["method_used"] == "keyword_fallback"
    assert result["hit_count"] == 2
    assert "Sansui AU-7900 service notes.txt" in result["sources"]
