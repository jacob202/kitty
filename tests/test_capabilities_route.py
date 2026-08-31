from fastapi.testclient import TestClient

from gateway import skill_registry
from gateway.app import app


def test_capabilities_projects_core_surfaces_and_discovered_skills(monkeypatch):
    monkeypatch.setattr(
        skill_registry,
        "discover",
        lambda: [{
            "name": "agent-council",
            "description": "Ask multiple agents for independent judgment.",
            "when_to_use": "hard decisions",
            "content": "SECRET SKILL BODY",
            "path": "/tmp/SKILL.md",
        }],
    )

    response = TestClient(app).get("/capabilities")

    assert response.status_code == 200
    capabilities = response.json()["capabilities"]
    by_id = {item["id"]: item for item in capabilities}
    assert {"home", "chat", "settings", "research"} <= set(by_id)
    assert by_id["research"]["view"] == "research"
    assert by_id["work"]["launch"] == "view"
    assert by_id["image-lab"]["view"] == "studio"
    assert by_id["skill:agent-council"] == {
        "id": "skill:agent-council",
        "label": "agent council",
        "description": "Ask multiple agents for independent judgment.",
        "category": "skills",
        "launch": "skill",
        "skill_name": "agent-council",
    }
    assert "SECRET SKILL BODY" not in response.text
    assert "/tmp/SKILL.md" not in response.text
