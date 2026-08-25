"""Regression coverage for concurrent health-domain collection."""

import asyncio

import pytest

from gateway.health_surface import HealthDomain, build_health_surface


@pytest.mark.asyncio
async def test_health_domains_are_collected_concurrently():
    first_started = asyncio.Event()
    second_started = asyncio.Event()

    async def first() -> HealthDomain:
        first_started.set()
        await second_started.wait()
        return HealthDomain("first", "available")

    async def second() -> HealthDomain:
        second_started.set()
        await first_started.wait()
        return HealthDomain("second", "available")

    sources = {"first": first, "second": second}
    result = await asyncio.wait_for(build_health_surface(sources), timeout=0.2)

    assert result["overall"] == "healthy"
    assert [domain["name"] for domain in result["domains"]] == ["first", "second"]
