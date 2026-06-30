"""Pool CRUD 烟雾 — ETF / Index / Stock pool add/list/remove + 搜索接口形状。"""
from __future__ import annotations

import pytest
from unittest.mock import patch


# ── ETF pool ─────────────────────────────────────────────────
def test_etf_list_default_pool_only(tmp_db):
    from backend.services.etf_service import ETFService
    pool = ETFService().list_pool()
    # init schema 不写入 DEFAULT_ETFS 到 DB, list_pool 总会返默认 4 个
    assert len(pool) == 4
    assert pool[0]["code"] == "510300"


def test_etf_add_and_remove(tmp_db):
    from backend.services.etf_service import ETFService
    ETFService.add_to_pool("512760", "国泰CES")
    ETFService.add_to_pool("512760", "国泰CES")  # 重复应幂等
    pool = ETFService().list_pool()
    codes = [e["code"] for e in pool]
    assert "512760" in codes
    assert codes.count("512760") == 1
    n = ETFService.remove_from_pool("512760")
    assert n == 1
    pool = ETFService().list_pool()
    assert "512760" not in [e["code"] for e in pool]


# ── Index pool ───────────────────────────────────────────────
def test_index_add_list_remove(tmp_db):
    from backend.services.index_service import IndexService
    IndexService.add_to_pool("sh.000300", "沪深300")
    IndexService.add_to_pool("sz.399006", "创业板指")
    pool = IndexService.list_pool()
    symbols = {r["symbol"] for r in pool}
    assert {"sh.000300", "sz.399006"} <= symbols
    assert IndexService.remove_from_pool("sh.000300") == 1
    assert "sh.000300" not in {r["symbol"] for r in IndexService.list_pool()}


def test_index_remove_from_cache(tmp_db):
    from backend.db.connection import get_connection
    from backend.services.index_service import IndexService
    conn = get_connection()
    conn.execute(
        """INSERT INTO kline_cache (symbol, freq, date, open, high, low, close,
           volume, amount, turnover, source, fetched_at)
           VALUES ('sh.000300','d','2026-06-29', 4000, 4010, 3995, 4005, 0, 0, 0, 'test', '2026-06-29T10:00:00')"""
    )
    conn.commit()
    assert IndexService.remove_from_cache("sh.000300") == 1
    assert IndexService.remove_from_cache("sh.000300") == 0  # 第二次 0 行


# ── Stock pool ───────────────────────────────────────────────
def test_stock_add_list_remove(tmp_db):
    from backend.services.stock_service import StockService
    StockService.add_to_pool("000001", "平安银行")
    StockService.add_to_pool("600519", "贵州茅台")
    pool = StockService.list_pool()
    codes = {r["code"] for r in pool}
    assert {"000001", "600519"} <= codes
    assert StockService.remove_from_pool("000001") == 1
    assert "000001" not in {r["code"] for r in StockService.list_pool()}


def test_stock_search_returns_list(tmp_db):
    """mock akshare 避免真网络。"""
    import pandas as pd
    from backend.services.stock_service import StockService
    fake = pd.DataFrame({"code": ["000001", "000002", "600519"], "name": ["平安银行", "万科A", "贵州茅台"]})
    with patch("akshare.stock_info_a_code_name", return_value=fake):
        results = StockService.search("平安")
    assert any(r["code"] == "000001" for r in results)
    # 空 query → 全返(前 50)
    with patch("akshare.stock_info_a_code_name", return_value=fake):
        results = StockService.search("")
    assert len(results) == 3