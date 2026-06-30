"""ETFService — ETF 份额时序 + 实时行情。

返回:
{
  "codes": ["510300", "510050", ...],
  "shares_timeseries": {
    "510300": [{"date": "2026-06-23", "shares": 12345678.0}, ...],
    ...
  },
  "realtime": {
    "510300": {"code": "510300", "name": "沪深300ETF", "close": 4.95, "change": 0.02, ...},
    ...
  }
}
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any

from backend.db.connection import get_connection
from backend.providers.registry import get_registry

log = logging.getLogger(__name__)


# 默认追踪的 ETF 池 (从 config 读, MVP 写死)
DEFAULT_ETFS = [
    {"code": "510300", "name": "沪深300ETF"},
    {"code": "510050", "name": "上证50ETF"},
    {"code": "510330", "name": "沪深300ETF(华夏)"},
    {"code": "510500", "name": "中证500ETF"},
]


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


class ETFService:
    def __init__(self) -> None:
        self.registry = get_registry()

    # ── pool 管理 ─────────────────────────────────────────────
    def list_pool(self) -> list[dict[str, Any]]:
        """合并 DEFAULT_ETFS + etf_pool 表, 去重保序。"""
        conn = get_connection()
        rows = conn.execute(
            "SELECT code, name FROM etf_pool ORDER BY added_at"
        ).fetchall()
        pool_codes = {e["code"] for e in DEFAULT_ETFS}
        out = list(DEFAULT_ETFS)
        for r in rows:
            if r["code"] not in pool_codes:
                out.append({"code": r["code"], "name": r["name"] or ""})
                pool_codes.add(r["code"])
        return out

    @staticmethod
    def add_to_pool(code: str, name: str | None) -> None:
        from datetime import datetime, timezone
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO etf_pool (code, name, added_at) VALUES (?, ?, ?)",
            (code, name or "", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()

    @staticmethod
    def remove_from_pool(code: str) -> int:
        conn = get_connection()
        cur = conn.execute("DELETE FROM etf_pool WHERE code = ?", (code,))
        conn.commit()
        return cur.rowcount

    @staticmethod
    async def search(q: str) -> list[dict[str, Any]]:
        """实时搜索: akshare fund_etf_spot_em, 前缀匹配 q。"""
        import akshare as ak
        df = ak.fund_etf_spot_em()
        q = (q or "").strip()
        if q:
            mask = df["代码"].astype(str).str.startswith(q) | df["名称"].astype(str).str.contains(q, na=False)
            df = df[mask]
        return [
            {"code": str(r["代码"]), "name": str(r["名称"])}
            for _, r in df.head(50).iterrows()
        ]

    async def get_overview(self, days: int = 30) -> dict[str, Any]:
        """一次性返回: ETF 池 + 份额时序 + 实时行情。"""
        pool = self.list_pool()
        # 1. 份额时序 (从 DB 优先)
        shares_ts = self._get_shares_from_db(pool, days)
        need_refresh_shares = any(
            len(shares_ts[e["code"]]) < 5 for e in pool
        )
        if need_refresh_shares:
            await self._refresh_shares_from_network(days)
            shares_ts = self._get_shares_from_db(pool, days)

        # 2. 实时行情 (从 DB 优先)
        realtime = self._get_realtime_from_db(pool)
        if not realtime:
            await self._refresh_realtime_from_network()
            realtime = self._get_realtime_from_db(pool)

        return {
            "codes": [e["code"] for e in pool],
            "shares_timeseries": shares_ts,
            "realtime": realtime,
        }

    async def get_data(self, days: int = 20, agg: str = "day", cache_only: bool = False) -> dict[str, Any]:
        """spec §6.1 /api/etf/data — days+agg+cache_only 参数版。
        区别于 overview: agg 决定份额时序聚合粒度 (day=原样, week=周五, month=月末)。
        """
        from backend.services.index_service import _aggregate_rows
        pool = self.list_pool()
        raw = self._get_shares_from_db(pool, days)
        if not cache_only and any(len(raw[e["code"]]) < 5 for e in pool):
            await self._refresh_shares_from_network(days)
            raw = self._get_shares_from_db(pool, days)
        # 聚合
        if agg != "day":
            agg_ts: dict[str, list] = {}
            for code, rows in raw.items():
                # 复用 _aggregate_rows: 倒序 → 升序 → 切尾
                rows_asc = list(reversed(rows))
                buckets = _aggregate_rows(rows_asc, agg, days)
                agg_ts[code] = buckets
        else:
            agg_ts = raw
        return {
            "codes": [e["code"] for e in pool],
            "agg": agg,
            "days": days,
            "shares_timeseries": agg_ts,
        }

    def _get_shares_from_db(self, etfs: list[dict], days: int) -> dict[str, list]:
        conn = get_connection()
        result = {}
        for e in etfs:
            rows = conn.execute(
                """
                SELECT date, shares FROM shares_cache
                WHERE code = ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (e["code"], days),
            ).fetchall()
            result[e["code"]] = [_row_to_dict(r) for r in reversed(rows)]
        return result

    def _get_realtime_from_db(self, etfs: list[dict]) -> dict[str, dict]:
        conn = get_connection()
        result = {}
        for e in etfs:
            row = conn.execute(
                """
                SELECT data, fetched_at FROM realtime_cache
                WHERE symbol = ? AND symbol_type = 'etf'
                """,
                (e["code"],),
            ).fetchone()
            if row:
                import json
                try:
                    data = json.loads(row["data"])
                    data["fetched_at"] = row["fetched_at"]
                    result[e["code"]] = data
                except json.JSONDecodeError:
                    pass
        return result

    async def _refresh_shares_from_network(self, days: int) -> None:
        """从 SSE + SZSE 拉 ETF 份额。"""
        date_to = date.today()
        date_from = date_to - timedelta(days=min(days * 2, 30))

        # SSE
        try:
            results = await self.registry.fetch_with_fallback(
                "etf_shares", date_from, date_to
            )
        except Exception as e:
            log.warning(f"[etf] SSE fetch failed: {e}")
            results = []

        if not results:
            return

        conn = get_connection()
        cur = conn.cursor()
        now_iso = results[0].fetched_at.isoformat(timespec="seconds")
        for r in results:
            if r.value is None:
                continue
            cur.execute(
                """
                INSERT OR REPLACE INTO shares_cache (code, date, shares, source, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (r.symbol, r.date.isoformat(), float(r.value), r.source, now_iso),
            )
        conn.commit()

    async def _refresh_realtime_from_network(self) -> None:
        """从 AkShare 拉 ETF 实时行情, 写 realtime_cache。"""
        primary = self.registry.get_primary("etf_realtime")
        if primary is None:
            log.warning("[etf] no provider for etf_realtime")
            return
        try:
            results = await primary.fetch(
                indicator="etf_realtime",
                date_from=date.today(),
                date_to=date.today(),
            )
        except Exception as e:
            log.warning(f"[etf] realtime fetch failed: {e}")
            return

        if not results:
            return

        import json
        conn = get_connection()
        cur = conn.cursor()
        now_iso = results[0].fetched_at.isoformat(timespec="seconds")
        for r in results:
            if r.symbol is None:
                continue
            data = r.fields or r.raw_data or {}
            data["code"] = r.symbol
            data["name"] = data.get("name", "")
            data["close"] = r.value
            cur.execute(
                """
                INSERT OR REPLACE INTO realtime_cache (symbol, symbol_type, fetched_at, data)
                VALUES (?, 'etf', ?, ?)
                """,
                (r.symbol, now_iso, json.dumps(data, default=str)),
            )
        conn.commit()