"""StockService 数据接口 — 单股 kline / fund_flow / summary / news。
akshare / baostock 全部 mock, 走单元路径。
"""
from __future__ import annotations

from datetime import date
from unittest.mock import patch, AsyncMock

import pandas as pd
import pytest


# ── helpers ──────────────────────────────────────────────────
def _fake_kline_result(symbol: str = "sz.000001"):
    """造一条 baostock 风格的 FetchResult。"""
    from backend.providers.base import FetchResult, KLineFreq
    return FetchResult(
        indicator="kline",
        date=date(2026, 6, 26),
        source="baostock",
        symbol=symbol,
        freq=KLineFreq.DAILY,
        fields={"open": 10.5, "high": 10.8, "low": 10.3, "close": 10.6,
                "volume": 1e8, "amount": 1.1e9, "turn": 0.5},
        fetched_at=__import__("datetime").datetime.now(),
        raw_data={},
    )


# ── kline ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_kline_cache_first_returns_cached(tmp_db):
    """kline_cache 已有 ≥5 行 → 不走网络。"""
    from backend.db.connection import get_connection
    from backend.services.stock_service import StockService
    conn = get_connection()
    for i in range(6):
        conn.execute(
            """INSERT INTO kline_cache (symbol, freq, date, open, high, low, close,
               volume, amount, turnover, source, fetched_at)
               VALUES ('sz.000001','d',?, 10, 11, 9.5, 10.5, 0, 0, 0, 'baostock', '2026-06-29T10:00:00')""",
            (f"2026-06-{20 + i:02d}",),
        )
    conn.commit()
    svc = StockService()
    with patch.object(svc.registry, "fetch_with_fallback", new=AsyncMock()) as m:
        rows = await svc.get_kline("000001", freq="d", limit=5)
    assert m.call_count == 0  # 没走网络
    assert len(rows) == 5
    assert rows[0]["date"] == "2026-06-21"
    assert rows[-1]["date"] == "2026-06-25"


@pytest.mark.asyncio
async def test_kline_cache_miss_fetches_and_writes(tmp_db):
    """cache 空 → 走网络 → 写库 → 返回。"""
    from backend.services.stock_service import StockService
    svc = StockService()
    fake_results = [_fake_kline_result("sz.000001")]
    with patch.object(svc.registry, "fetch_with_fallback",
                      new=AsyncMock(return_value=fake_results)):
        rows = await svc.get_kline("000001", freq="d", limit=5)
    assert len(rows) == 1
    assert rows[0]["symbol" if "symbol" in rows[0] else "source"] == "baostock" \
        or rows[0]["source"] == "baostock"
    assert rows[0]["close"] == 10.6
    # 写库成功
    from backend.db.connection import get_connection
    n = get_connection().execute(
        "SELECT COUNT(*) AS n FROM kline_cache WHERE symbol='sz.000001'"
    ).fetchone()["n"]
    assert n == 1


@pytest.mark.asyncio
async def test_kline_handles_603_and_688_as_sh(tmp_db):
    """600/603/688 → sh.xxx 前缀。"""
    from backend.services.stock_service import StockService, _a_share_symbol
    assert _a_share_symbol("600519") == "sh.600519"
    assert _a_share_symbol("688981") == "sh.688981"
    assert _a_share_symbol("000001") == "sz.000001"
    assert _a_share_symbol("300750") == "sz.300750"
    assert _a_share_symbol("sh.600519") == "sh.600519"  # 已带前缀


@pytest.mark.asyncio
async def test_kline_invalid_freq_raises(tmp_db):
    from backend.services.stock_service import StockService
    with pytest.raises(ValueError, match="freq must be"):
        await StockService().get_kline("000001", freq="x")


# ── fund_flow ────────────────────────────────────────────────
def test_fund_flow_filters_by_code():
    """akshare 返全市场表 → 服务筛 code。"""
    from backend.services.stock_service import StockService
    fake = pd.DataFrame({
        "代码": ["000001", "000002"],
        "名称": ["平安银行", "万科A"],
        "最新价": [10.5, 8.2],
        "涨跌幅": [1.2, -0.5],
        "主力净流入-净额": [1e8, -5e7],
        "主力净流入-净占比": [5.0, -2.0],
        "超大单净流入-净额": [3e7, -1e7],
        "大单净流入-净额": [7e7, -4e7],
        "中单净流入-净额": [-2e7, 1e7],
        "小单净流入-净额": [-8e7, 4e7],
    })
    with patch("akshare.stock_individual_fund_flow_rank", return_value=fake):
        rows = StockService.get_fund_flow("000001")
    assert len(rows) == 1
    r = rows[0]
    assert r["code"] == "000001"
    assert r["main_net_inflow"] == 1e8
    assert r["small_net_inflow"] == -8e7


# ── summary ──────────────────────────────────────────────────
def test_summary_returns_dict_or_empty():
    from backend.services.stock_service import StockService
    fake = pd.DataFrame({
        "代码": ["000001"],
        "名称": ["平安银行"],
        "最新价": [10.5], "涨跌幅": [1.2], "涨跌额": [0.12],
        "成交量": [1.2e8], "成交额": [1.3e9], "振幅": [2.5],
        "最高": [10.8], "最低": [10.3], "今开": [10.4], "昨收": [10.38],
        "换手率": [0.6], "市盈率-动态": [5.2], "市净率": [0.6],
        "总市值": [2e11], "流通市值": [2e11],
    })
    with patch("akshare.stock_zh_a_spot_em", return_value=fake):
        d = StockService.get_summary("000001")
    assert d["code"] == "000001"
    assert d["close"] == 10.5
    assert d["pe"] == 5.2

    # 找不到 → {}
    with patch("akshare.stock_zh_a_spot_em", return_value=fake):
        d = StockService.get_summary("999999")
    assert d == {}


# ── news ─────────────────────────────────────────────────────
def test_news_returns_list():
    from backend.services.stock_service import StockService
    fake = pd.DataFrame({
        "新闻标题": [f"标题{i}" for i in range(5)],
        "发布时间": ["2026-06-29 10:00:00"] * 5,
        "文章来源": ["财联社"] * 5,
        "新闻链接": [f"http://example.com/{i}" for i in range(5)],
    })
    with patch("akshare.stock_news_em", return_value=fake):
        rows = StockService.get_news("000001", limit=3)
    assert len(rows) == 3
    assert rows[0]["title"] == "标题0"
    assert rows[0]["url"] == "http://example.com/0"


def test_news_handles_akshare_failure():
    """akshare 偶发抛错 → 返空 list, 不应抛。"""
    from backend.services.stock_service import StockService
    with patch("akshare.stock_news_em", side_effect=Exception("rate limit")):
        rows = StockService.get_news("000001")
    assert rows == []


# ── realtime (Sina) ──────────────────────────────────────────
@pytest.mark.asyncio
async def test_realtime_parses_sina_payload(tmp_db):
    from backend.services.stock_service import StockService
    """mock httpx 返 Sina 原始 payload → 解析出 2 只。"""
    fake_resp = (
        'var hq_str_sz000001="平安银行,10.22,10.23,10.24,10.32,10.02,10.23,10.24,'
        '112413978,1144166877.64,167800,10.23,749700,10.22,290300,10.21,555700,'
        '10.20,80000,10.19,189160,10.24,432800,10.25,1093900,10.26,83100,10.27,'
        '480600,10.28,2026-06-29,15:00:00,00";\n'
        'var hq_str_sh600519="贵州茅台,1169.0,1168.63,1194.96,1215.0,1151.01,'
        '1194.96,1194.98,6687812,7949237761,69,1194.96,2200,1194.95,100,1194.94,'
        '100,1194.93,300,1194.92,2137,1194.97,2300,1194.98,3100,1194.99,600,'
        '1195.00,500,1195.01,2026-06-29,15:00:04,00,";\n'
    )
    fake = AsyncMock()
    fake.text = fake_resp
    fake.raise_for_status = lambda: None
    fake_ctx = AsyncMock()
    fake_ctx.get = AsyncMock(return_value=fake)
    fake_ctx.__aenter__ = AsyncMock(return_value=fake_ctx)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=fake_ctx):
        out = await StockService.get_realtime_batch(["000001", "600519"])
    assert set(out.keys()) == {"000001", "600519"}
    assert out["000001"]["price"] == 10.24
    assert out["000001"]["change_pct"] == pytest.approx(0.098, abs=1e-3)
    assert out["600519"]["name"] == "贵州茅台"
    assert out["600519"]["price"] == 1194.96


@pytest.mark.asyncio
async def test_realtime_empty_codes_returns_empty(tmp_db):
    from backend.services.stock_service import StockService
    out = await StockService.get_realtime_batch([])
    assert out == {}


@pytest.mark.asyncio
async def test_realtime_handles_http_failure(tmp_db):
    """Sina 502 → 返空 dict, 不应抛。"""
    from backend.services.stock_service import StockService
    fake_ctx = AsyncMock()
    fake_ctx.get = AsyncMock(side_effect=Exception("timeout"))
    fake_ctx.__aenter__ = AsyncMock(return_value=fake_ctx)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=fake_ctx):
        out = await StockService.get_realtime_batch(["000001"])
    assert out == {}


# ── minute (Tencent) ─────────────────────────────────────────
@pytest.mark.asyncio
async def test_minute_parses_tencent_payload(tmp_db):
    from backend.services.stock_service import StockService
    fake_json = {
        "code": 0, "msg": "",
        "data": {"sz000001": {"data": {"data": [
            "0930 10.22 6117 6251574.00",
            "0931 10.14 42507 43227250.00",
            "1500 10.24 1124140 1144167101.56",
        ]}}},
    }
    fake = AsyncMock()
    fake.json = lambda: fake_json
    fake.raise_for_status = lambda: None
    fake_ctx = AsyncMock()
    fake_ctx.get = AsyncMock(return_value=fake)
    fake_ctx.__aenter__ = AsyncMock(return_value=fake_ctx)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=fake_ctx):
        out = await StockService.get_minute("000001")
    assert len(out) == 3
    assert out[0]["time"] == "0930"
    assert out[0]["price"] == 10.22
    assert out[0]["avg_price"] == 10.22  # 第一条 amount/vol/100 = 10.22
    assert out[-1]["time"] == "1500"


@pytest.mark.asyncio
async def test_minute_handles_empty_payload(tmp_db):
    from backend.services.stock_service import StockService
    fake = AsyncMock()
    fake.json = lambda: {"code": 0, "data": {"sz000001": {"data": {"data": []}}}}
    fake.raise_for_status = lambda: None
    fake_ctx = AsyncMock()
    fake_ctx.get = AsyncMock(return_value=fake)
    fake_ctx.__aenter__ = AsyncMock(return_value=fake_ctx)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=fake_ctx):
        out = await StockService.get_minute("000001")
    assert out == []


@pytest.mark.asyncio
async def test_minute_handles_http_failure(tmp_db):
    from backend.services.stock_service import StockService
    fake_ctx = AsyncMock()
    fake_ctx.get = AsyncMock(side_effect=Exception("net err"))
    fake_ctx.__aenter__ = AsyncMock(return_value=fake_ctx)
    fake_ctx.__aexit__ = AsyncMock(return_value=False)
    with patch("httpx.AsyncClient", return_value=fake_ctx):
        out = await StockService.get_minute("000001")
    assert out == []


# ── _sina_symbol ─────────────────────────────────────────────
def test_sina_symbol_prefix_mapping():
    from backend.services.stock_service import _sina_symbol
    assert _sina_symbol("600519") == "sh600519"
    assert _sina_symbol("688981") == "sh688981"
    assert _sina_symbol("000001") == "sz000001"
    assert _sina_symbol("300750") == "sz300750"
    assert _sina_symbol("sz.000001") == "sz000001"  # 已带点 → 去点
    assert _sina_symbol("sh.600519") == "sh600519"