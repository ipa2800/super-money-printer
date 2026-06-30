"""IndexService — 指数 K线业务逻辑。

MVP 行为:
1. 先查 kline_cache 表 (近 limit 天), 命中且 source='baostock' 则直接返回
2. 未命中 → 走 registry fetch_with_fallback → 写库 → 返回
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, timedelta
from typing import Any, Optional

from backend.db.connection import get_connection
from backend.providers.base import FetchResult, KLineFreq
from backend.providers.registry import get_registry

log = logging.getLogger(__name__)


FREQ_MAP = {
    "d": KLineFreq.DAILY,
    "w": KLineFreq.WEEKLY,
    "m": KLineFreq.MONTHLY,
}


def _row_to_dict(row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


class IndexService:
    def __init__(self) -> None:
        self.registry = get_registry()

    async def get_kline(
        self,
        symbol: str,
        freq: str = "d",
        limit: int = 60,
    ) -> list[dict[str, Any]]:
        """获取某指数的 K线数据, limit 控制返回最近 N 条。"""
        freq_enum = FREQ_MAP.get(freq)
        if freq_enum is None:
            raise ValueError(f"invalid freq: {freq}, expected one of d/w/m")

        # ── 先查 DB ──
        conn = get_connection()
        cached = conn.execute(
            """
            SELECT date, open, high, low, close, volume, amount, turnover, source
            FROM kline_cache
            WHERE symbol = ? AND freq = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (symbol, freq, limit),
        ).fetchall()
        if len(cached) >= min(limit, 5):  # 命中阈值: 至少 5 行才认为有效
            return [_row_to_dict(r) for r in reversed(cached)]

        # ── 未命中 → 拉网络 ──
        date_to = date.today()
        # 多拉一些 buffer,防止 limit 截断后损失
        date_from = date_to - timedelta(days=limit * 3)
        results: list[FetchResult] = await self.registry.fetch_with_fallback(
            indicator="kline",
            date_from=date_from,
            date_to=date_to,
            freq=freq_enum,
            symbol=symbol,
        )
        if not results:
            return []

        # 写库
        now_iso = results[0].fetched_at.isoformat(timespec="seconds")
        cur = conn.cursor()
        for r in results:
            f = r.fields or {}
            cur.execute(
                """
                INSERT OR REPLACE INTO kline_cache
                    (symbol, freq, date, open, high, low, close,
                     volume, amount, turnover, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    r.symbol, freq, r.date.isoformat(),
                    f.get("open"), f.get("high"), f.get("low"), f.get("close"),
                    f.get("volume"), f.get("amount"), f.get("turn"),
                    r.source, now_iso,
                ),
            )
        conn.commit()

        # 返回最近 limit 条
        rows = conn.execute(
            """
            SELECT date, open, high, low, close, volume, amount, turnover, source
            FROM kline_cache
            WHERE symbol = ? AND freq = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (symbol, freq, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in reversed(rows)]

    async def backfill(self, symbol: str, freq: str, start_date: date, end_date: date) -> int:
        """拉指定日期范围历史数据并写库。返回写入行数。"""
        freq_enum = FREQ_MAP.get(freq)
        if freq_enum is None:
            raise ValueError(f"invalid freq: {freq}")
        try:
            results = await self.registry.fetch_with_fallback(
                "kline", start_date, end_date, freq=freq_enum, symbol=symbol,
            )
        except Exception as e:
            log.warning(f"[backfill {symbol}/{freq}] fetch failed: {e}")
            return 0
        return _write_kline_results(results, source="backfill")

    @staticmethod
    def list_cached_symbols() -> list[dict[str, Any]]:
        """kline_cache GROUP BY symbol, freq — 给 /api/index/cache/list。"""
        conn = get_connection()
        rows = conn.execute(
            """SELECT symbol, freq, MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS n
               FROM kline_cache GROUP BY symbol, freq ORDER BY symbol, freq"""
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── pool 管理 ────────────────────────────────────────────
    @staticmethod
    def list_pool() -> list[dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute("SELECT symbol, name FROM index_pool ORDER BY added_at").fetchall()
        return [_row_to_dict(r) for r in rows]

    @staticmethod
    def add_to_pool(symbol: str, name: str | None) -> None:
        from datetime import datetime, timezone
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO index_pool (symbol, name, added_at) VALUES (?, ?, ?)",
            (symbol, name or "", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()

    @staticmethod
    def remove_from_pool(symbol: str) -> int:
        conn = get_connection()
        cur = conn.execute("DELETE FROM index_pool WHERE symbol = ?", (symbol,))
        conn.commit()
        return cur.rowcount

    @staticmethod
    def remove_from_cache(symbol: str) -> int:
        """从 kline_cache 删, 不动 index_pool。"""
        conn = get_connection()
        cur = conn.execute("DELETE FROM kline_cache WHERE symbol = ?", (symbol,))
        conn.commit()
        return cur.rowcount

    # ── days + agg 聚合 (spec §6.1: /api/index/data) ──────────
    async def get_data(self, days: int = 20, agg: str = "day", symbol: str | None = None) -> list[dict[str, Any]]:
        """返回最近 N 天 K线, 按 agg 聚合 (day=原样, week=周五, month=月末)。"""
        from datetime import date, timedelta
        freq = {"day": "d", "week": "w", "month": "m"}.get(agg, "d")
        if symbol is None:
            return []
        date_to = date.today()
        date_from = date_to - timedelta(days=days * 3)  # 多拉 buffer
        try:
            results = await self.registry.fetch_with_fallback(
                "kline", date_from, date_to, freq=KLineFreq.DAILY, symbol=symbol,
            )
        except Exception:
            results = []
        if not results:
            return []
        # 落库
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
                (r.symbol, "d", r.date.isoformat(),
                 fld.get("open"), fld.get("high"), fld.get("low"), fld.get("close"),
                 fld.get("volume"), fld.get("amount"), fld.get("turn"),
                 r.source, now_iso),
            )
        conn.commit()
        rows = conn.execute(
            """SELECT date, open, high, low, close, volume FROM kline_cache
               WHERE symbol = ? AND freq = 'd' ORDER BY date DESC LIMIT ?""",
            (symbol, days * 3),
        ).fetchall()
        rows = list(reversed(rows))
        if freq == "d":
            return [_row_to_dict(r) for r in rows[-days:]]
        # 聚合 week/month
        return _aggregate_rows(rows, agg, days)


def _aggregate_rows(rows: list, agg: str, limit: int) -> list[dict[str, Any]]:
    """week=取每周最后一行, month=每月最后一行。"""
    from datetime import date as _date
    if agg == "week":
        buckets: dict[tuple[int, int], dict] = {}
        for r in rows:
            d = _date.fromisoformat(r["date"])
            y, w, _ = d.isocalendar()
            key = (y, w)
            if key not in buckets or r["date"] > buckets[key]["date"]:
                buckets[key] = _row_to_dict(r)
        out = sorted(buckets.values(), key=lambda x: x["date"])
        return out[-limit:]
    if agg == "month":
        buckets2: dict[tuple[int, int], dict] = {}
        for r in rows:
            d = _date.fromisoformat(r["date"])
            key = (d.year, d.month)
            if key not in buckets2 or r["date"] > buckets2[key]["date"]:
                buckets2[key] = _row_to_dict(r)
        out = sorted(buckets2.values(), key=lambda x: x["date"])
        return out[-limit:]
    return [_row_to_dict(r) for r in rows[-limit:]]


def _write_kline_results(results, source: str = "kline") -> int:
    """把 fetch 结果批量写 kline_cache, 返回写入行数。"""
    if not results:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    now_iso = results[0].fetched_at.isoformat(timespec="seconds")
    n = 0
    for r in results:
        fld = r.fields or {}
        if r.freq:
            freq_v = r.freq.value if hasattr(r.freq, "value") else str(r.freq)
        else:
            freq_v = "d"
        cur.execute(
            """INSERT OR REPLACE INTO kline_cache
               (symbol, freq, date, open, high, low, close,
                volume, amount, turnover, source, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (r.symbol, freq_v, r.date.isoformat(),
             fld.get("open"), fld.get("high"), fld.get("low"), fld.get("close"),
             fld.get("volume"), fld.get("amount"), fld.get("turn"),
             r.source or source, now_iso),
        )
        n += 1
    conn.commit()
    return n