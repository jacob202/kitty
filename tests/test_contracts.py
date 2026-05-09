"""Verify contract schemas are importable and valid."""
from contracts.routing_decision import RoutingDecision, ModelTier
from datetime import datetime


def test_routing_decision_creates():
    decision = RoutingDecision(
        correlation_id="test-123",
        domain="soul",
        sensitivity="low",
        model_tier=ModelTier.DEFAULT,
        model_name="kitty-default",
        reasoning="General query, no sensitive content detected.",
    )
    assert decision.correlation_id == "test-123"
    assert decision.model_tier == ModelTier.DEFAULT
    assert isinstance(decision.timestamp, datetime)


def test_routing_decision_medical_tier():
    decision = RoutingDecision(
        correlation_id="test-456",
        domain="health",
        sensitivity="medical",
        model_tier=ModelTier.PRIVATE,
        model_name="kitty-private",
        reasoning="Medical query detected — routing to local MLX model only.",
    )
    assert decision.model_tier == ModelTier.PRIVATE
    assert decision.sensitivity == "medical"
