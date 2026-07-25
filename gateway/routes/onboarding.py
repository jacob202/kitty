"""Persisted onboarding state endpoint."""

from pydantic import BaseModel

from fastapi import APIRouter

from gateway.onboarding import get_onboarding_state, set_onboarding_state

class OnboardingOnboardingResponse(BaseModel):
    model_config = {"extra": "allow"}


class OnboardingOnboardingResponse(BaseModel):
    model_config = {"extra": "allow"}



router = APIRouter(tags=["onboarding"])


@router.get("/onboarding", response_model=OnboardingOnboardingResponse)
def get_onboarding():
    return get_onboarding_state()


@router.post("/onboarding", response_model=OnboardingOnboardingResponse)
def post_onboarding(body: dict):
    onboarded = body.get("onboarded")
    preferred_name = body.get("preferredName")
    theme = body.get("theme")
    return set_onboarding_state(
        onboarded=onboarded,
        preferred_name=preferred_name,
        theme=theme,
    )
