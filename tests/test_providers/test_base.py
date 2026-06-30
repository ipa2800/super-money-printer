"""BaseProvider 抽象契约测试。"""
from __future__ import annotations

import pytest

from backend.providers.base import BaseProvider, FetchResult, KLineFreq


def test_base_provider_cannot_instantiate_directly():
    """BaseProvider 是抽象类, 直接实例化必须抛 TypeError。"""
    with pytest.raises(TypeError):
        BaseProvider()  # type: ignore[abstract]


def test_kline_freq_values():
    """KLineFreq 枚举值稳定 (被 DB 存储依赖)。"""
    assert KLineFreq.DAILY.value == "d"
    assert KLineFreq.WEEKLY.value == "w"
    assert KLineFreq.MONTHLY.value == "m"


def test_fetch_result_defaults():
    """FetchResult 默认值合理。"""
    from datetime import date
    r = FetchResult(indicator="kline", date=date(2026, 1, 1), source="test")
    assert r.confidence == 1.0
    assert r.freq is None
    assert r.fields is None
    assert r.symbol is None
    assert r.value is None