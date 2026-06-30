"""BaostockProvider 真实网络调用测试。

注意: 需要 baostock 网络可达, 默认匿名登录。
"""
from __future__ import annotations

import asyncio
from datetime import date, timedelta

import pytest

from backend.providers.base import KLineFreq
from backend.providers.baostock import BaostockProvider


@pytest.fixture
def provider():
    p = BaostockProvider()
    p.login()
    yield p
    p.logout()


def test_provider_metadata(provider):
    """Provider 元数据符合预期。"""
    assert provider.name == "baostock"
    assert "kline" in provider.supported_indicators
    assert KLineFreq.DAILY in provider.supports_freq
    assert KLineFreq.WEEKLY in provider.supports_freq
    assert KLineFreq.MONTHLY in provider.supports_freq


def test_health_check(provider):
    """健康检查返回 HealthReport, status 至少是 healthy/degraded 之一。"""
    from backend.providers.base import ProviderStatus
    h = provider.health_check()
    assert h.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED)
    assert h.error_count >= 0


@pytest.mark.asyncio
async def test_fetch_kline_real_network(provider):
    """真实调 baostock 拿沪深300 最近 30 个交易日。"""
    date_to = date.today()
    date_from = date_to - timedelta(days=60)
    results = await provider.fetch(
        indicator="kline",
        date_from=date_from,
        date_to=date_to,
        freq=KLineFreq.DAILY,
        symbol="sh.000300",
    )
    assert len(results) > 0, "expected at least some kline rows from baostock"
    r = results[0]
    assert r.indicator == "kline"
    assert r.source == "baostock"
    assert r.symbol == "sh.000300"
    assert r.freq == KLineFreq.DAILY
    assert r.fields is not None
    for col in ("open", "high", "low", "close"):
        assert col in r.fields
        assert isinstance(r.fields[col], float)


@pytest.mark.asyncio
async def test_fetch_unsupported_indicator(provider):
    """不支持的 indicator 抛 DataNotAvailableError。"""
    from backend.providers.exceptions import DataNotAvailableError
    with pytest.raises(DataNotAvailableError):
        await provider.fetch(
            indicator="macro_pmi",
            date_from=date(2026, 1, 1),
            date_to=date(2026, 1, 2),
        )