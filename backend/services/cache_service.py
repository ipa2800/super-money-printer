"""CacheService — 缓存状态/范围/回填/清理。spec §7.4, §9.3.4。"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from backend.db.connection import get_connection

log = logging.getLogger(__name__)


# spec §9.3.4 — 各指标 stale 阈值 (秒)
INDICATOR_TTL = {
    "kline_daily":  20 * 3600,
    "etf_realtime": 120,
    "etf_shares":   20 * 3600,
    "mainflow":     25 * 3600,
    "bond_10y":     25 * 3600,
    "shibor_on":    25 * 3600,
    "usd_cny":      25 * 3600,
    "pmi_mfg":      32 * 86400,
    "m2":           35 * 86400,
    "cpi":          35 * 86400,
    "lpr":          35 * 86400,
}


def _status_for(last_success: str | None, ttl_seconds: int) -> str:
    """success / stale / never / failed 状态计算。
    failed: provider_health 表连续 5 次 error。
    """
    if last_success is None:
        return "never"
    try:
        last_dt = datetime.fromisoformat(last_success)
    except (ValueError, TypeError):
        return "never"
    now = datetime.now()
    if last_dt.tzinfo is not None:
        last_dt = last_dt.replace(tzinfo=None)
    age = (now - last_dt).total_seconds()
    if age > ttl_seconds:
        return "stale"
    return "success"


def _is_provider_failed(scope: str) -> bool:
    """scope ∈ {kline, macro, etf_shares, etf_realtime} — 对应 provider error_count >= 5 算 failed。"""
    mapping = {
        "kline": "baostock",
        "macro": "akshare",
        "etf_shares": "sse",
        "etf_realtime": "akshare",
    }
    name = mapping.get(scope)
    if not name:
        return False
    conn = get_connection()
    row = conn.execute(
        "SELECT error_count FROM provider_health WHERE provider = ?", (name,),
    ).fetchone()
    if not row:
        return False
    return (row["error_count"] or 0) >= 5


class CacheService:
    # ── /api/cache/status ─────────────────────────────────────────────
    @staticmethod
    def get_status() -> dict[str, Any]:
        conn = get_connection()
        now_iso = datetime.now().isoformat(timespec="seconds")
        items: list[dict] = []
        # provider 健康快查 — 容忍没有 error_count 列(测试库/老 schema)
        health_failed: set[str] = set()
        try:
            cols = [r["name"] for r in conn.execute("PRAGMA table_info(provider_health)").fetchall()]
            if "error_count" in cols:
                rows = conn.execute(
                    "SELECT provider FROM provider_health WHERE error_count >= 5"
                ).fetchall()
                health_failed = {r["provider"] for r in rows}
        except Exception:
            health_failed = set()

        # 1. macro_cache: 按 indicator 分组, 取每组最新 fetched_at
        macro_rows = conn.execute(
            """SELECT indicator, MAX(fetched_at) AS last_success, COUNT(*) AS n
               FROM macro_cache GROUP BY indicator"""
        ).fetchall()
        for r in macro_rows:
            ttl = INDICATOR_TTL.get(r["indicator"], 25 * 3600)
            status = _status_for(r["last_success"], ttl)
            if status == "success" and "akshare" in health_failed:
                status = "failed"
            items.append({
                "scope": "macro",
                "key":   r["indicator"],
                "last_success": r["last_success"],
                "status": status,
                "ttl_seconds": ttl,
                "row_count": r["n"],
            })

        # 2. kline_cache: 按 (symbol, freq) 分组
        kline_rows = conn.execute(
            """SELECT symbol, freq, MAX(fetched_at) AS last_success, COUNT(*) AS n
               FROM kline_cache GROUP BY symbol, freq"""
        ).fetchall()
        for r in kline_rows:
            ttl = INDICATOR_TTL["kline_daily"]
            status = _status_for(r["last_success"], ttl)
            if status == "success" and ("baostock" in health_failed or "tushare" in health_failed):
                status = "failed"
            items.append({
                "scope": "kline",
                "key":   f"{r['symbol']}/{r['freq']}",
                "last_success": r["last_success"],
                "status": status,
                "ttl_seconds": ttl,
                "row_count": r["n"],
            })

        # 3. shares_cache: 按 code 分组
        share_rows = conn.execute(
            """SELECT code, MAX(fetched_at) AS last_success, COUNT(*) AS n
               FROM shares_cache GROUP BY code"""
        ).fetchall()
        for r in share_rows:
            ttl = INDICATOR_TTL["etf_shares"]
            status = _status_for(r["last_success"], ttl)
            if status == "success" and ("sse" in health_failed or "szse" in health_failed):
                status = "failed"
            items.append({
                "scope": "etf_shares",
                "key":   r["code"],
                "last_success": r["last_success"],
                "status": status,
                "ttl_seconds": ttl,
                "row_count": r["n"],
            })

        # 4. realtime_cache: 整张表
        rt_row = conn.execute(
            "SELECT MAX(fetched_at) AS last_success, COUNT(*) AS n FROM realtime_cache"
        ).fetchone()
        if rt_row["n"] > 0:
            ttl = INDICATOR_TTL["etf_realtime"]
            status = _status_for(rt_row["last_success"], ttl)
            if status == "success" and "akshare" in health_failed:
                status = "failed"
            items.append({
                "scope": "etf_realtime",
                "key":   "ALL",
                "last_success": rt_row["last_success"],
                "status": status,
                "ttl_seconds": ttl,
                "row_count": rt_row["n"],
            })

        return {"now": now_iso, "items": items}

    # ── /api/cache/ranges ─────────────────────────────────────────────
    @staticmethod
    def get_ranges() -> dict[str, Any]:
        conn = get_connection()
        out: dict[str, Any] = {}

        for table, key_col in [("kline_cache", "symbol"), ("shares_cache", "code"),
                               ("macro_cache", "indicator"), ("realtime_cache", None)]:
            if key_col:
                rows = conn.execute(
                    f"""SELECT {key_col} AS k, MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS n
                        FROM {table} GROUP BY {key_col}"""
                ).fetchall()
                for r in rows:
                    out.setdefault(table, {})[r["k"]] = {
                        "min_date": r["min_date"], "max_date": r["max_date"], "count": r["n"],
                    }
            else:
                row = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()
                out[table] = {"ALL": {"count": row["n"]}}
        return out

    # ── /api/cache/clear ──────────────────────────────────────────────
    @staticmethod
    def clear(scope: str, key: str | None = None) -> int:
        """scope ∈ {kline, shares, macro, realtime}. key 可选."""
        conn = get_connection()
        table_map = {"kline": "kline_cache", "shares": "shares_cache",
                     "macro": "macro_cache", "realtime": "realtime_cache"}
        table = table_map.get(scope)
        if not table:
            raise ValueError(f"unknown scope: {scope}")
        if key is None:
            cur = conn.execute(f"DELETE FROM {table}")
        elif scope == "kline":
            symbol, _, freq = key.partition("/")
            if not freq:
                freq = "d"
            cur = conn.execute(
                "DELETE FROM kline_cache WHERE symbol = ? AND freq = ?",
                (symbol, freq),
            )
        elif scope == "shares":
            cur = conn.execute("DELETE FROM shares_cache WHERE code = ?", (key,))
        elif scope == "macro":
            cur = conn.execute("DELETE FROM macro_cache WHERE indicator = ?", (key,))
        elif scope == "realtime":
            cur = conn.execute("DELETE FROM realtime_cache WHERE symbol = ?", (key,))
        conn.commit()
        return cur.rowcount

    # ── /api/cache/backfill (K线历史回填) ─────────────────────────────
    @staticmethod
    async def backfill_kline(symbol: str, freq: str = "d", days: int = 365) -> dict[str, Any]:
        """用 BaostockProvider 拉历史 N 天, 写 kline_cache."""
        from backend.providers.registry import get_registry
        from backend.providers.base import KLineFreq
        from backend.services.index_service import _write_kline_results

        freq_map = {"d": KLineFreq.DAILY, "w": KLineFreq.WEEKLY, "m": KLineFreq.MONTHLY}
        if freq not in freq_map:
            raise ValueError(f"freq must be d/w/m, got {freq!r}")

        date_to = datetime.now().date()
        date_from = date_to - timedelta(days=days)
        registry = get_registry()
        try:
            results = await registry.fetch_with_fallback(
                "kline", date_from, date_to, freq=freq_map[freq], symbol=symbol,
            )
        except Exception as e:
            return {"symbol": symbol, "freq": freq, "n_written": 0, "error": str(e)[:200]}
        n = _write_kline_results(results, source="backfill")
        return {"symbol": symbol, "freq": freq, "days": days, "n_written": n}

    # ── /api/cache/refresh (复用 scheduler.trigger) ──────────────────
    @staticmethod
    async def refresh(job_id: str | None = None) -> str:
        from backend.scheduler.jobs import run_job
        if job_id is None:
            # 全跑 (l0/l1/l2/l3)
            results = []
            for jid in ("l0_realtime", "l1_daily", "l3_evening"):
                results.append(f"{jid}={await run_job(jid)}")
            return "; ".join(results)
        return await run_job(job_id)