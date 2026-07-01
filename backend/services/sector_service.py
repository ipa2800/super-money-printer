"""SectorService — 板块/概念 (行业+概念) 业务逻辑.

snapshot:  从 sector_cache 读全部; 空则触发 fetch_with_fallback + 写库.
history:   从 sector_history 读单板块; 空/不足则触发 fetch_with_fallback + 写库.
scheduler 负责定期刷新 (l4_sector).
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from backend.db.connection import get_connection
from backend.providers.base import FetchResult
from backend.providers.registry import get_registry

log = logging.getLogger(__name__)


def _row_to_dict(row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


class SectorService:
    def __init__(self) -> None:
        self.registry = get_registry()

    # ── 快照: 全量 ──
    async def get_snapshot(self) -> list[dict[str, Any]]:
        """返回所有板块/概念的实时快照. 缓存空时回源拉一次."""
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT code, type, name, price, change, pct_chg, total_mv, turnover,
                   up_count, down_count, leader, leader_pct, source, fetched_at
            FROM sector_cache
            ORDER BY type, pct_chg DESC
            """
        ).fetchall()
        if rows:
            return [_row_to_dict(r) for r in rows]

        # 空 → 回源拉
        log.info("[sector] cache empty, fetching snapshot")
        results = await self.registry.fetch_with_fallback(
            indicator="sector_snapshot",
            date_from=date.today(),
            date_to=date.today(),
        )
        if not results:
            return []
        self._save_snapshot(results)
        rows = conn.execute(
            """
            SELECT code, type, name, price, change, pct_chg, total_mv, turnover,
                   up_count, down_count, leader, leader_pct, source, fetched_at
            FROM sector_cache
            ORDER BY type, pct_chg DESC
            """
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    def _save_snapshot(self, results: list[FetchResult]) -> None:
        conn = get_connection()
        now_iso = results[0].fetched_at.isoformat(timespec="seconds")
        cur = conn.cursor()
        for r in results:
            # symbol 格式 'industry:BK0473', 拆出来
            if not r.symbol or ":" not in r.symbol:
                continue
            stype, code = r.symbol.split(":", 1)
            f = r.fields or {}
            cur.execute(
                """
                INSERT OR REPLACE INTO sector_cache
                    (code, type, name, price, change, pct_chg, total_mv, turnover,
                     up_count, down_count, leader, leader_pct, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code, stype,
                    f.get("name"), f.get("price"), f.get("change"), f.get("pct_chg"),
                    f.get("total_mv"), f.get("turnover"),
                    f.get("up_count"), f.get("down_count"),
                    f.get("leader"), f.get("leader_pct"),
                    r.source, now_iso,
                ),
            )
        conn.commit()

    async def refresh_snapshot(self) -> int:
        """scheduler 调用: 主动拉一次快照并覆盖 cache. 返回写入条数."""
        results = await self.registry.fetch_with_fallback(
            indicator="sector_snapshot",
            date_from=date.today(),
            date_to=date.today(),
        )
        if not results:
            return 0
        self._save_snapshot(results)
        return len(results)

    # ── 历史: 单板块 ──
    async def get_history(
        self,
        symbol: str,                # 'industry:BK0473' | 'concept:BKXXXX'
        days: int = 180,
        agg: str = "day",           # day|week|month — 前端传, 服务层做聚合
    ) -> list[dict[str, Any]]:
        """返回单个板块的时序 (按 days 截尾, agg 决定粒度)."""
        if ":" not in symbol:
            return []
        stype, code = symbol.split(":", 1)

        conn = get_connection()
        # 行数: 日 ≈ days, 周 ≈ days/7, 月 ≈ days/30. 多取 buffer.
        if agg == "week":
            limit = max(8, days // 7)
        elif agg == "month":
            limit = max(6, days // 30)
        else:
            limit = days

        rows = conn.execute(
            """
            SELECT date, open, close, high, low, volume, amount, pct_chg, change, source
            FROM sector_history
            WHERE code = ? AND type = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (code, stype, limit),
        ).fetchall()

        if len(rows) >= limit * 0.8:  # 缓存够 80% 才直接返回
            return [_row_to_dict(r) for r in reversed(rows)]

        # 不够 → 拉网络
        date_to = date.today()
        date_from = date_to - timedelta(days=max(days, 180))  # 多拉半年兜底
        try:
            results = await self.registry.fetch_with_fallback(
                indicator="sector_history",
                date_from=date_from,
                date_to=date_to,
                symbol=symbol,
            )
        except Exception as e:
            log.warning(f"[sector] history fetch failed for {symbol}: {e}")
            if rows:
                return [_row_to_dict(r) for r in reversed(rows)]
            return []

        if results:
            self._save_history(results)
        rows = conn.execute(
            """
            SELECT date, open, close, high, low, volume, amount, pct_chg, change, source
            FROM sector_history
            WHERE code = ? AND type = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (code, stype, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in reversed(rows)]

    def _save_history(self, results: list[FetchResult]) -> None:
        conn = get_connection()
        cur = conn.cursor()
        for r in results:
            if not r.symbol or ":" not in r.symbol:
                continue
            stype, code = r.symbol.split(":", 1)
            f = r.fields or {}
            cur.execute(
                """
                INSERT OR REPLACE INTO sector_history
                    (code, type, date, open, close, high, low,
                     volume, amount, pct_chg, change, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    code, stype, r.date.isoformat(),
                    f.get("open"), f.get("close"), f.get("high"), f.get("low"),
                    f.get("volume"), f.get("amount"),
                    f.get("pct_chg"), f.get("change"),
                    r.source, r.fetched_at.isoformat(timespec="seconds"),
                ),
            )
        conn.commit()

    async def refresh_all_history(self, delay_sec: float = 0.3) -> dict[str, int]:
        """scheduler 调用: 给 cache 中所有板块拉历史. 串行+小 delay 避免被封.
        返回 {'industry': N, 'concept': M} 写入条数."""
        import asyncio
        conn = get_connection()
        rows = conn.execute(
            "SELECT DISTINCT code, type FROM sector_cache"
        ).fetchall()
        ok = {"industry": 0, "concept": 0}
        fail = 0
        for r in rows:
            symbol = f"{r['type']}:{r['code']}"
            try:
                date_to = date.today()
                date_from = date_to - timedelta(days=180)
                results = await self.registry.fetch_with_fallback(
                    indicator="sector_history",
                    date_from=date_from,
                    date_to=date_to,
                    symbol=symbol,
                )
                if results:
                    self._save_history(results)
                    ok[r['type']] = ok.get(r['type'], 0) + len(results)
            except Exception as e:
                fail += 1
                log.debug(f"[sector] history fail {symbol}: {e}")
            await asyncio.sleep(delay_sec)
        log.info(f"[sector] history refresh ok={ok} fail={fail}")
        return ok