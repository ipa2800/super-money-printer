"""ProviderRegistry 单元测试。"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional

import pytest

from backend.providers.base import (
    BaseProvider,
    FetchResult,
    HealthReport,
    KLineFreq,
    ProviderStatus,
)
from backend.providers.exceptions import ProviderError
from backend.providers.registry import ProviderRegistry


@dataclass
class FakeProvider(BaseProvider):
    name: str = "fake"
    display_name: str = "Fake"
    priority: int = 1
    supports_freq: list[KLineFreq] = field(default_factory=list)
    supported_indicators: set[str] = field(default_factory=lambda: {"fake_indicator"})
    fail: bool = False
    unhealthy: bool = False

    async def fetch(self, indicator, date_from, date_to,
                    freq: Optional[KLineFreq] = None,
                    symbol: Optional[str] = None):
        if self.fail:
            raise ProviderError(self.name, "fake fail")
        return [FetchResult(indicator=indicator, date=date(2026, 1, 1), source=self.name)]

    def health_check(self):
        if self.unhealthy:
            return HealthReport(ProviderStatus.UNAVAILABLE, 0, None, 0, "down")
        return HealthReport(ProviderStatus.HEALTHY, 0, None, 0, "ok")


def test_register_sorts_by_priority():
    reg = ProviderRegistry()
    p_high = FakeProvider(name="p_high", priority=1)
    p_low = FakeProvider(name="p_low", priority=9)
    reg.register(p_low)
    reg.register(p_high)
    all_p = reg.get_all("fake_indicator")
    assert all_p[0].name == "p_high"
    assert all_p[1].name == "p_low"


def test_get_primary_skips_unhealthy():
    reg = ProviderRegistry()
    p1 = FakeProvider(name="p1", priority=1, unhealthy=True)
    p2 = FakeProvider(name="p2", priority=2)
    reg.register(p1)
    reg.register(p2)
    primary = reg.get_primary("fake_indicator")
    assert primary is not None
    assert primary.name == "p2"


@pytest.mark.asyncio
async def test_fetch_with_fallback_on_primary_failure():
    reg = ProviderRegistry()
    p1 = FakeProvider(name="p1", priority=1, fail=True)
    p2 = FakeProvider(name="p2", priority=2)
    reg.register(p1)
    reg.register(p2)
    results = await reg.fetch_with_fallback(
        "fake_indicator", date(2026, 1, 1), date(2026, 1, 2)
    )
    assert len(results) == 1
    assert results[0].source == "p2"


@pytest.mark.asyncio
async def test_fetch_with_fallback_raises_when_all_fail():
    reg = ProviderRegistry()
    p1 = FakeProvider(name="p1", priority=1, fail=True)
    reg.register(p1)
    with pytest.raises(ProviderError):
        await reg.fetch_with_fallback(
            "fake_indicator", date(2026, 1, 1), date(2026, 1, 2)
        )


def test_get_status_shape():
    reg = ProviderRegistry()
    reg.register(FakeProvider(name="p1", priority=1))
    s = reg.get_status()
    assert "providers" in s
    assert "summary" in s
    assert "p1" in s["providers"]
    assert s["providers"]["p1"]["status"] == "healthy"
    assert s["summary"]["healthy"] == 1