"""Unit tests for TL-02: gateway process freshness check."""
import time

from gateway.doctor import _check_gateway_freshness


def test_warns_when_process_predates_source():
    now = time.time()
    process_start = now - 120  # started 2 minutes ago
    source_mtime = now - 30    # source changed 30 seconds ago

    checks = _check_gateway_freshness(process_start=process_start, source_mtime=source_mtime)

    assert len(checks) == 1
    assert checks[0].level == "WARN"
    assert checks[0].name == "runtime:gateway_freshness"
    assert "restart" in checks[0].detail


def test_passes_when_process_is_newer_than_source():
    now = time.time()
    process_start = now - 10   # started 10 seconds ago
    source_mtime = now - 120   # source last touched 2 minutes ago

    checks = _check_gateway_freshness(process_start=process_start, source_mtime=source_mtime)

    assert len(checks) == 1
    assert checks[0].level == "PASS"
    assert checks[0].name == "runtime:gateway_freshness"


def test_passes_when_gateway_not_running():
    checks = _check_gateway_freshness(process_start=None, source_mtime=time.time())

    assert len(checks) == 1
    assert checks[0].level == "PASS"
    assert "not running" in checks[0].detail


def test_passes_when_source_mtime_equals_process_start():
    ts = time.time() - 60
    checks = _check_gateway_freshness(process_start=ts, source_mtime=ts)

    assert checks[0].level == "PASS"
