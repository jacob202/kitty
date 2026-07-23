"""Persisted onboarding state endpoint."""

from fastapi import APIRouter
from gateway.onboarding import get_onboarding_state, set_onboarding_state

router = APIRouter(tags=["onboarding"])


@router.get("/onboarding")
def get_onboarding():
    return get_onboarding_state()


@router.post("/onboarding")
def post_onboarding(body: dict):
    onboarded = body.get("onboarded")
    preferred_name = body.get("preferredName")
    theme = body.get("theme")
    return set_onboarding_state(
        onboarded=onboarded,
        preferred_name=preferred_name,
        theme=theme,
    )
