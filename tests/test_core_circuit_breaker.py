from src.core.circuit_breaker import CircuitBreaker, CircuitBreakerConfig


def test_circuit_opens_after_windowed_failure_threshold(tmp_path):
    db_path = tmp_path / "circuit.db"
    breaker = CircuitBreaker(
        "test-provider",
        config=CircuitBreakerConfig(
            failure_threshold=3,
            recovery_timeout=60,
            failure_window=300,
        ),
        db_path=db_path,
    )

    assert breaker.is_open() is False

    breaker.record_failure("first")
    breaker.record_failure("second")
    assert breaker.is_open() is False

    breaker.record_failure("third")

    assert breaker.is_open() is True
