from fastapi.testclient import TestClient

from gateway import skill_registry
from gateway.app import app


def test_capabilities_projects_core_surfaces_and_only_chat_launchable_skills(monkeypatch):
    calls = []

    def discover(*, force_refresh=False):
        calls.append(force_refresh)
        return [
            {
                "name": "safe-guide",
                "description": "Guide the model without external execution.",
                "when_to_use": "reasoning help",
                "content": "SAFE BODY",
                "path": "/tmp/safe/SKILL.md",
                "chat_launchable": True,
            },
            {
                "name": "image-gen",
                "description": "Requires an image endpoint.",
                "when_to_use": "make images",
                "content": "TOOL BODY",
                "path": "/tmp/tool/SKILL.md",
                "chat_launchable": False,
            },
        ]

    monkeypatch.setattr(skill_registry, "discover", discover)

    response = TestClient(app).get("/capabilities")

    assert response.status_code == 200
    assert calls == [True]
    capabilities = response.json()["capabilities"]
    by_id = {item["id"]: item for item in capabilities}
    assert {"home", "chat", "settings", "research"} <= set(by_id)
    assert by_id["research"]["view"] == "research"
    assert by_id["work"]["launch"] == "view"
    assert by_id["image-lab"]["view"] == "studio"
    assert by_id["skill:safe-guide"] == {
        "id": "skill:safe-guide",
        "label": "safe guide",
        "description": "Guide the model without external execution.",
        "category": "skills",
        "launch": "skill",
        "skill_name": "safe-guide",
    }
    assert "skill:image-gen" not in by_id
    assert "SAFE BODY" not in response.text
    assert "/tmp/safe/SKILL.md" not in response.text
