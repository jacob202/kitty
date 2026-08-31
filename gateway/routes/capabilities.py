"""Read-only projection of Kitty capabilities for product discovery."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from gateway import skill_registry

router = APIRouter(tags=["capabilities"])


class Capability(BaseModel):
    id: str
    label: str
    description: str
    category: str
    launch: str
    view: str | None = None
    skill_name: str | None = None


_CORE_CAPABILITIES = (
    Capability(id="home", label="home", description="See what matters now and what Kitty recommends next.", category="navigate", launch="view", view="home"),
    Capability(id="chat", label="chat", description="Open the main Kitty conversation workspace.", category="navigate", launch="view", view="chat"),
    Capability(id="work", label="work", description="Run and inspect delegated Kitty work.", category="work", launch="view", view="work"),
    Capability(id="projects", label="projects", description="Resume a project with its context and outputs.", category="work", launch="view", view="projects"),
    Capability(id="image-lab", label="image lab", description="Create, edit, compare, and reuse images.", category="create", launch="view", view="studio"),
    Capability(id="library", label="library", description="Find documents and durable Kitty artifacts.", category="knowledge", launch="view", view="library"),
    Capability(id="automations", label="automations", description="Inspect and manage recurring or scheduled work.", category="automate", launch="view", view="automations"),
    Capability(id="agents", label="agents", description="Open Kitty's shared agent workspace.", category="work", launch="view", view="agents"),
    Capability(id="tutor", label="tutor", description="Learn with Kitty's tutoring workspace.", category="knowledge", launch="view", view="tutor"),
    Capability(id="journal", label="journal", description="Write and revisit journal entries.", category="personal", launch="view", view="journal"),
    Capability(id="settings", label="settings", description="Manage Kitty runtime, providers, tools, and preferences.", category="navigate", launch="view", view="settings"),
)


def _skill_capability(skill: dict) -> Capability:
    name = str(skill.get("name", "")).strip()
    description = str(skill.get("description", "") or skill.get("when_to_use", "") or "Use this installed Kitty skill.").strip()
    return Capability(
        id=f"skill:{name}",
        label=name.replace("-", " "),
        description=description,
        category="skills",
        launch="skill",
        skill_name=name,
    )


@router.get("/capabilities")
async def list_capabilities():
    skills = [_skill_capability(skill) for skill in skill_registry.discover() if str(skill.get("name", "")).strip()]
    skills.sort(key=lambda item: item.label)
    return {"capabilities": [*map(lambda item: item.model_dump(exclude_none=True), _CORE_CAPABILITIES), *map(lambda item: item.model_dump(exclude_none=True), skills)]}
