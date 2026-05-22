from gateway import mcp_council_server


def test_consult_council_returns_final_response(monkeypatch):
    class FakeGraph:
        def invoke(self, state):
            assert state == {"query": "How do I fix this amp?", "messages": []}
            return {"final_response": "Use the council summary."}

    monkeypatch.setattr(mcp_council_server, "_get_council_graph", lambda: FakeGraph())

    response = mcp_council_server.dispatch(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": "consult_council",
                "arguments": {"query": "How do I fix this amp?"},
            },
        }
    )

    assert response["result"]["response"] == "Use the council summary."
    assert response["result"]["content"][0]["text"] == "Use the council summary."
