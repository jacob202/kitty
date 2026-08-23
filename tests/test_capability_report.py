"""Tests for QoL Packet 07: startup capability report.

RED contract: every test exercises the public API of
``gateway.capability_report`` — ``Capability``, ``CapabilityReport``,
``build_capability_report``, ``render_capability_report`` and the async
``probe_capabilities``.
"""

from __future__ import annotations

import pytest

from gateway import capability_report as cr


def _cap(name: str, status: str, **kw) -> cr.Capability:
    return cr.Capability(name=name, status=status, **kw)


def _all_available() -> dict[str, cr.Capability]:
    return {
        "Gateway": _cap("Gateway", cr.AVAILABLE),
        "Database": _cap("Database", cr.AVAILABLE),
        "Memory": _cap("Memory", cr.AVAILABLE),
        "Automation": _cap("Automation", cr.AVAILABLE),
        "Image Lab": _cap("Image Lab", cr.AVAILABLE),
        "Image Queue": _cap("Image Queue", cr.AVAILABLE),
        "Telegram": _cap("Telegram", cr.AVAILABLE),
        "Ollama": _cap("Ollama", cr.AVAILABLE, optional=True),
    }


class TestVocabulary:
    def test_status_vocabulary_bounded(self):
        assert cr.VALID_STATUSES == {
            "available",
            "degraded",
            "unavailable",
            "optional-unavailable",
            "unknown",
        }


class TestBuildCapabilityReport:
    def test_clean_install_all_available(self):
        report = cr.build_capability_report(_all_available())
        assert [c.name for c in report.capabilities] == [
            "Gateway",
            "Database",
            "Memory",
            "Automation",
            "Image Lab",
            "Image Queue",
            "Telegram",
            "Ollama",
        ]
        assert report.overall == cr.AVAILABLE
        assert set(report.still_functional) == {
            "Explicit memory",
            "Pinned context",
            "Image generation",
            "Scheduled automation",
        }

    def test_unknown_status_handled(self):
        probes = _all_available()
        probes["Automation"] = _cap("Automation", cr.UNKNOWN)
        report = cr.build_capability_report(probes)
        assert report.overall == cr.DEGRADED
        assert set(report.still_functional) == {
            "Explicit memory",
            "Pinned context",
            "Image generation",
        }

    def test_extra_optional_dependency_preserved_in_order(self):
        probes = _all_available()
        probes["Another Dep"] = _cap("Another Dep", cr.AVAILABLE, optional=True)
        report = cr.build_capability_report(probes)
        assert report.capabilities[-1].name == "Another Dep"


class TestRenderCapabilityReport:
    def test_clean_install_renders_all_checks_and_no_degraded(self):
        report = cr.build_capability_report(_all_available())
        text = cr.render_capability_report(report)
        assert "KITTY READY" in text
        for cap in report.capabilities:
            assert cap.name in text
        assert "Degraded" not in text
        assert "Explicit memory" in text
        assert "Pinned context" in text
        assert "Image generation" in text
        assert "Scheduled automation" in text

    def test_ollama_absent_keeps_memory_features(self):
        probes = _all_available()
        probes["Ollama"] = _cap("Ollama", cr.OPTIONAL_UNAVAILABLE, optional=True)
        report = cr.build_capability_report(probes)
        text = cr.render_capability_report(report)
        assert "Degraded" in text
        assert "unavailable" in text
        assert set(report.still_functional) == {
            "Explicit memory",
            "Pinned context",
            "Image generation",
            "Scheduled automation",
        }

    def test_image_provider_unavailable_drops_image_generation(self):
        probes = _all_available()
        probes["Image Lab"] = _cap("Image Lab", cr.UNAVAILABLE)
        report = cr.build_capability_report(probes)
        text = cr.render_capability_report(report)
        assert "Degraded" in text
        assert "Image Lab" in text
        assert "Image generation" not in report.still_functional
        assert "Explicit memory" in report.still_functional

    def test_telegram_unavailable_rendered_in_degraded(self):
        probes = _all_available()
        probes["Telegram"] = _cap("Telegram", cr.UNAVAILABLE)
        report = cr.build_capability_report(probes)
        text = cr.render_capability_report(report)
        assert "Degraded" in text
        assert "Telegram" in text
        assert "Telegram" not in report.available

    def test_database_failure_drops_memory_features(self):
        probes = _all_available()
        probes["Database"] = _cap("Database", cr.UNAVAILABLE)
        probes["Memory"] = _cap("Memory", cr.UNAVAILABLE, detail="database unreachable")
        report = cr.build_capability_report(probes)
        text = cr.render_capability_report(report)
        assert "Database" in text
        assert set(report.still_functional) == {"Image generation", "Scheduled automation"}

    def test_multiple_degraded_reflects_surviving_features(self):
        probes = _all_available()
        probes["Database"] = _cap("Database", cr.UNAVAILABLE)
        probes["Memory"] = _cap("Memory", cr.UNAVAILABLE)
        probes["Image Lab"] = _cap("Image Lab", cr.DEGRADED)
        probes["Image Queue"] = _cap("Image Queue", cr.DEGRADED)
        report = cr.build_capability_report(probes)
        text = cr.render_capability_report(report)
        assert "Degraded" in text
        assert report.still_functional == ["Scheduled automation"]

    def test_unknown_rendered_as_unknown(self):
        probes = _all_available()
        probes["Automation"] = _cap("Automation", cr.UNKNOWN)
        report = cr.build_capability_report(probes)
        text = cr.render_capability_report(report)
        assert "Automation" in text
        assert "unknown" in text


class TestProbeCapabilities:
    @pytest.mark.asyncio
    async def test_probe_capabilities_maps_real_probes(self, monkeypatch):
        probe_calls: list[str] = []

        class _FakeBackend:
            async def is_available(self) -> bool:
                return False

        import gateway.image_backends as ib

        async def _probe_database():
            probe_calls.append("database")
            return True

        def _fake_probe_memory_backend():
            probe_calls.append("memory")
            return object()

        async def _fake_ollama():
            probe_calls.append("ollama")
            return cr.OPTIONAL_UNAVAILABLE

        monkeypatch.setattr(cr, "_probe_database", _probe_database)
        monkeypatch.setattr(cr, "_probe_memory_backend", _fake_probe_memory_backend)
        monkeypatch.setattr(cr, "_probe_ollama", _fake_ollama)
        monkeypatch.setattr(ib.get_registry(), "get_all", lambda: [_FakeBackend()])
        monkeypatch.setattr(
            cr,
            "_supervisor_status",
            lambda name: {"status": "available", "reason": "ok"},
        )

        report = await cr.probe_capabilities()
        assert probe_calls == ["database", "memory", "ollama"]
        names = [c.name for c in report.capabilities]
        assert names[0] == "Gateway"
        assert "Database" in names and "Image Lab" in names and "Ollama" in names
        by_name = {c.name: c for c in report.capabilities}
        assert by_name["Database"].status == cr.AVAILABLE
        assert by_name["Memory"].status == cr.AVAILABLE
        assert by_name["Image Lab"].status == cr.UNAVAILABLE
        assert by_name["Ollama"].status == cr.OPTIONAL_UNAVAILABLE

    @pytest.mark.asyncio
    async def test_probe_memory_degraded_when_only_backend_fails(self, monkeypatch):
        from gateway.memory import MemoryError

        async def _probe_database():
            return True

        def _fake_probe_memory_backend():
            raise MemoryError("mem0ai is not installed")

        async def _fake_ollama():
            return cr.OPTIONAL_UNAVAILABLE

        async def _fake_image_lab():
            return cr.UNAVAILABLE

        monkeypatch.setattr(cr, "_probe_database", _probe_database)
        monkeypatch.setattr(cr, "_probe_memory_backend", _fake_probe_memory_backend)
        monkeypatch.setattr(cr, "_probe_ollama", _fake_ollama)
        monkeypatch.setattr(cr, "_probe_image_lab", _fake_image_lab)
        monkeypatch.setattr(
            cr,
            "_supervisor_status",
            lambda name: {"status": "available", "reason": "ok"},
        )

        report = await cr.probe_capabilities()
        by_name = {c.name: c for c in report.capabilities}
        assert by_name["Memory"].status == cr.DEGRADED
        assert by_name["Database"].status == cr.AVAILABLE
        assert "Explicit memory" in report.still_functional
