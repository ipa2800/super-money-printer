"""macro_service + etf_service 烟雾测试 — 用 tmp_db, 不走网络。"""
from __future__ import annotations

import asyncio
import json
from datetime import date

import pytest

from backend.db.connection import get_connection
from backend.services.etf_service import ETFService
from backend.services.macro_service import MacroService


@pytest.fixture
def service_db(tmp_db):
    """建好 schema + 种入几条 sample 行, 模拟已刷新过的状态。"""
    conn = get_connection()
    # macro_cache: 8 indicators 各 5 天
    rows = [
        ("mainflow", "2026-06-25", -200.0, "akshare"),
        ("mainflow", "2026-06-26", -300.0, "akshare"),
        ("mainflow", "2026-06-29", -495.34, "akshare"),
        ("bond_10y", "2026-06-29", 1.717, "akshare"),
        ("usd_cny",  "2026-06-29", 6.8175, "akshare"),
        ("m2",       "2026-05-01", 8.6, "akshare"),
        ("cpi",      "2026-05-01", 1.2, "akshare"),
        ("lpr",      "2026-06-22", 3.0, "akshare"),
    ]
    cur = conn.cursor()
    for ind, d, v, src in rows:
        cur.execute(
            "INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
            (ind, d, v, src, "2026-06-29T10:00:00"),
        )
    # shares_cache: 1 ETF × 3 天
    for d, s in [("2026-06-25", 200.0), ("2026-06-26", 210.0), ("2026-06-29", 220.0)]:
        cur.execute(
            "INSERT INTO shares_cache (code, date, shares, source, fetched_at) VALUES (?,?,?,?,?)",
            ("510300", d, s, "sse", "2026-06-29T10:00:00"),
        )
    # realtime_cache: 1 ETF
    rt_data = {"code": "510300", "name": "沪深300ETF", "close": 4.95, "change": 0.05, "pct_chg": 1.02}
    cur.execute(
        "INSERT INTO realtime_cache (symbol, symbol_type, fetched_at, data) VALUES (?,?,?,?)",
        ("510300", "etf", "2026-06-29T10:00:00", json.dumps(rt_data)),
    )
    conn.commit()
    return conn


def test_macro_service_returns_8_cards(service_db, monkeypatch):
    """种了 8 indicator 行 → get_cards 返回 8 个 card。"""
    # 关掉网络刷新, 测试只走 DB 路径
    async def noop(*a, **kw):
        return None
    monkeypatch.setattr(MacroService, "_refresh_from_network", noop)

    svc = MacroService()
    result = asyncio.run(svc.get_cards())
    assert "cards" in result
    assert len(result["cards"]) == 8
    by_ind = {c["indicator"]: c for c in result["cards"]}
    assert by_ind["mainflow"]["value"] == -495.34
    assert by_ind["mainflow"]["date"] == "2026-06-29"
    assert by_ind["usd_cny"]["value"] == 6.8175
    assert by_ind["lpr_1y"]["value"] == 3.0


def test_etf_service_returns_shares_and_realtime(service_db):
    """种了 1 ETF × 3 days shares + realtime → get_overview 返回。"""
    svc = ETFService()
    result = asyncio.run(svc.get_overview(days=30))
    assert "510300" in result["codes"]
    assert len(result["shares_timeseries"]["510300"]) == 3
    assert result["realtime"]["510300"]["close"] == 4.95


def test_etf_service_empty_db_returns_empty(tmp_db):
    """空 DB → shares_timeseries 是空 list (不抛异常)。"""
    svc = ETFService()
    result = asyncio.run(svc.get_overview(days=30))
    for code in result["codes"]:
        assert result["shares_timeseries"][code] == []