"""StockService — 自选股池 CRUD + 个股数据 (kline/fund_flow/summary/news)。"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from backend.db.connection import get_connection
from backend.providers.base import KLineFreq
from backend.providers.registry import get_registry

log = logging.getLogger(__name__)


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


class StockService:
    def __init__(self) -> None:
        self.registry = get_registry()

    # ── pool CRUD ────────────────────────────────────────────
    @staticmethod
    def list_pool() -> list[dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT code, name FROM stock_pool ORDER BY added_at"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    @staticmethod
    def add_to_pool(code: str, name: str | None) -> None:
        from datetime import datetime, timezone
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO stock_pool (code, name, added_at) VALUES (?, ?, ?)",
            (code, name or "", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()

    @staticmethod
    def remove_from_pool(code: str) -> int:
        conn = get_connection()
        cur = conn.execute("DELETE FROM stock_pool WHERE code = ?", (code,))
        conn.commit()
        return cur.rowcount

    @staticmethod
    def search(q: str) -> list[dict[str, Any]]:
        """akshare stock_info_a_code_name — 全市场代码表, 前缀/包含匹配。"""
        import akshare as ak
        df = ak.stock_info_a_code_name()
        q = (q or "").strip()
        if q:
            mask = df["code"].astype(str).str.startswith(q) | df["name"].astype(str).str.contains(q, na=False)
            df = df[mask]
        return [
            {"code": str(r["code"]), "name": str(r["name"])}
            for _, r in df.head(50).iterrows()
        ]

    # ── 单股数据 ─────────────────────────────────────────────
    async def get_kline(self, code: str, freq: str = "d", limit: int = 60) -> list[dict[str, Any]]:
        """BaostockProvider 拉日/周/月 K线。code 接受 'sh.600000' 或 '600000'。"""
        freq_map = {"d": KLineFreq.DAILY, "w": KLineFreq.WEEKLY, "m": KLineFreq.MONTHLY}
        f = freq_map.get(freq)
        if f is None:
            raise ValueError(f"freq must be d/w/m, got {freq!r}")
        symbol = _a_share_symbol(code)
        date_to = date.today()
        date_from = date_to - timedelta(days=limit * 3)
        results = await self.registry.fetch_with_fallback(
            "kline", date_from, date_to, freq=f, symbol=symbol,
        )
        if not results:
            return []
        conn = get_connection()
        cur = conn.cursor()
        now_iso = results[0].fetched_at.isoformat(timespec="seconds")
        for r in results:
            fld = r.fields or {}
            cur.execute(
                """INSERT OR REPLACE INTO kline_cache
                   (symbol, freq, date, open, high, low, close,
                    volume, amount, turnover, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, freq, r.date.isoformat(),
                 fld.get("open"), fld.get("high"), fld.get("low"), fld.get("close"),
                 fld.get("volume"), fld.get("amount"), fld.get("turn"),
                 r.source, now_iso),
            )
        conn.commit()
        rows = conn.execute(
            """SELECT date, open, high, low, close, volume, amount, turnover, source
               FROM kline_cache WHERE symbol = ? AND freq = ?
               ORDER BY date DESC LIMIT ?""",
            (symbol, freq, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in reversed(rows)]

    @staticmethod
    def get_fund_flow(code: str) -> list[dict[str, Any]]:
        """akshare stock_individual_fund_flow_rank — 取该 code 当日。"""
        import akshare as ak
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        rows = df[df["代码"].astype(str) == code]
        return [
            {"name": str(r["名称"]), "code": str(r["代码"]),
             "close": float(r.get("最新价", 0) or 0),
             "change_pct": float(r.get("涨跌幅", 0) or 0),
             "main_net_inflow": float(r.get("主力净流入-净额", 0) or 0),
             "main_net_inflow_pct": float(r.get("主力净流入-净占比", 0) or 0),
             "super_net_inflow": float(r.get("超大单净流入-净额", 0) or 0),
             "big_net_inflow": float(r.get("大单净流入-净额", 0) or 0),
             "medium_net_inflow": float(r.get("中单净流入-净额", 0) or 0),
             "small_net_inflow": float(r.get("小单净流入-净额", 0) or 0)}
            for _, r in rows.iterrows()
        ]

    @staticmethod
    def get_summary(code: str) -> dict[str, Any]:
        """akshare stock_zh_a_spot_em — 筛 code。"""
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        rows = df[df["代码"].astype(str) == code]
        if rows.empty:
            return {}
        r = rows.iloc[0]
        return {
            "code": str(r["代码"]),
            "name": str(r["名称"]),
            "close": float(r.get("最新价", 0) or 0),
            "change_pct": float(r.get("涨跌幅", 0) or 0),
            "change": float(r.get("涨跌额", 0) or 0),
            "volume": float(r.get("成交量", 0) or 0),
            "amount": float(r.get("成交额", 0) or 0),
            "amplitude": float(r.get("振幅", 0) or 0),
            "high": float(r.get("最高", 0) or 0),
            "low": float(r.get("最低", 0) or 0),
            "open": float(r.get("今开", 0) or 0),
            "prev_close": float(r.get("昨收", 0) or 0),
            "turnover_rate": float(r.get("换手率", 0) or 0),
            "pe": float(r.get("市盈率-动态", 0) or 0),
            "pb": float(r.get("市净率", 0) or 0),
            "market_cap": float(r.get("总市值", 0) or 0),
            "float_cap": float(r.get("流通市值", 0) or 0),
        }

    @staticmethod
    def get_news(code: str, limit: int = 10) -> list[dict[str, Any]]:
        """akshare stock_news_em — 10 条。"""
        import akshare as ak
        try:
            df = ak.stock_news_em(symbol=code)
        except Exception as e:
            log.warning(f"[stock {code}] news fetch failed: {e}")
            return []
        return [
            {"title": str(r.get("新闻标题", "")), "time": str(r.get("发布时间", "")),
             "source": str(r.get("文章来源", "")), "url": str(r.get("新闻链接", ""))}
            for _, r in df.head(limit).iterrows()
        ]


def _a_share_symbol(code: str) -> str:
    """A 股代码 → baostock 格式 (sh.600000 / sz.000001)。
    600/601/603/605/688 = 沪市; 000/001/002/300 = 深市; 8/4 开头 = 北交所 (sz. 暂用)。
    已带 . 前缀直接返回。
    """
    if "." in code:
        return code
    if code.startswith(("60", "688", "9")):
        return f"sh.{code}"
    return f"sz.{code}"