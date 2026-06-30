"""Scheduler jobs — 每个 layer 一个 async 函数, 失败写 task_log。"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from backend.db.connection import get_connection
from backend.providers.registry import get_registry
from backend.providers.base import FetchResult
from backend.services.etf_service import DEFAULT_ETFS

log = logging.getLogger(__name__)


# ── 工具 ──────────────────────────────────────────────────────────────
async def _fetch_one(indicator: str, days_back: int = 30) -> list[FetchResult]:
    """registry.fetch_with_fallback 包一层, 出错返回 []。"""
    registry = get_registry()
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)
    try:
        return await registry.fetch_with_fallback(indicator, date_from, date_to)
    except Exception as e:
        log.warning(f"[scheduler] fetch {indicator} failed: {e}")
        return []


def _write_macro(results: list[FetchResult]) -> int:
    """写 macro_cache, 返回写入行数。"""
    if not results:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    now_iso = results[0].fetched_at.isoformat(timespec="seconds")
    n = 0
    for r in results:
        if r.value is None:
            continue
        cur.execute(
            "INSERT OR REPLACE INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
            (r.indicator, r.date.isoformat(), float(r.value), r.source, now_iso),
        )
        n += 1
    conn.commit()
    return n


def _write_shares(results: list[FetchResult]) -> int:
    if not results:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    now_iso = results[0].fetched_at.isoformat(timespec="seconds")
    n = 0
    for r in results:
        if r.value is None or r.symbol is None:
            continue
        cur.execute(
            "INSERT OR REPLACE INTO shares_cache (code, date, shares, source, fetched_at) VALUES (?,?,?,?,?)",
            (r.symbol, r.date.isoformat(), float(r.value), r.source, now_iso),
        )
        n += 1
    conn.commit()
    return n


def _write_realtime(results: list[FetchResult]) -> int:
    """写 realtime_cache, ETF 全市场。"""
    import json
    if not results:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    now_iso = results[0].fetched_at.isoformat(timespec="seconds")
    n = 0
    for r in results:
        if r.symbol is None:
            continue
        data = r.fields or r.raw_data or {}
        data["code"] = r.symbol
        data["close"] = r.value
        cur.execute(
            "INSERT OR REPLACE INTO realtime_cache (symbol, symbol_type, fetched_at, data) VALUES (?,?,?,?)",
            (r.symbol, "etf", now_iso, json.dumps(data, default=str)),
        )
        n += 1
    conn.commit()
    return n


# ── L0 实时: ETF 实时行情 (每分钟) ──────────────────────────────────
async def job_l0_realtime() -> str:
    """每分钟刷新 ETF 实时行情。"""
    log.info("[L0] realtime start")
    results = await _fetch_one("etf_realtime", days_back=1)
    n = _write_realtime(results)
    log.info(f"[L0] realtime done: {n} ETFs")
    return f"wrote {n} ETFs"


# ── L1 日终: ETF 份额 (16:05) ──────────────────────────────────────
async def job_l1_daily() -> str:
    """日终结算: ETF 份额 + 主要指数 K线。"""
    log.info("[L1] daily start")
    shares = await _fetch_one("etf_shares", days_back=30)
    n_shares = _write_shares(shares)
    # 同时刷实时 (16:05 后用盘后数据)
    rt = await _fetch_one("etf_realtime", days_back=1)
    n_rt = _write_realtime(rt)
    log.info(f"[L1] daily done: shares={n_shares} realtime={n_rt}")
    return f"shares={n_shares}, realtime={n_rt}"


# ── L2 月初: 月频宏观 (PMI/M2/CPI/LPR) ─────────────────────────────
async def job_l2_monthly() -> str:
    log.info("[L2] monthly start")
    summary = []
    for ind in ("pmi_mfg", "m2", "cpi", "lpr"):
        # 月频拉 14 个月覆盖 sparkline
        results = await _fetch_one(ind, days_back=420)
        n = _write_macro(results)
        summary.append(f"{ind}={n}")
    log.info(f"[L2] monthly done: {', '.join(summary)}")
    return ", ".join(summary)


# ── L3 傍晚: 日频宏观 (主力/国债/SHIBOR/美元) ──────────────────────
async def job_l3_evening() -> str:
    log.info("[L3] evening start")
    summary = []
    for ind in ("mainflow", "bond_10y", "shibor_on", "usd_cny"):
        results = await _fetch_one(ind, days_back=30)
        n = _write_macro(results)
        summary.append(f"{ind}={n}")
    log.info(f"[L3] evening done: {', '.join(summary)}")
    return ", ".join(summary)


# ── Job → handler 映射 ───────────────────────────────────────────────
JOB_HANDLERS = {
    "l0_realtime": job_l0_realtime,
    "l1_daily":    job_l1_daily,
    "l2_monthly":  job_l2_monthly,
    "l3_evening":  job_l3_evening,
}


async def run_job(job_id: str) -> str:
    """调一个 job, 写 task_log, 广播 start/done/error 到 progress bus。"""
    import time
    from datetime import datetime
    from backend.scheduler.bus import get_bus

    handler = JOB_HANDLERS.get(job_id)
    if handler is None:
        raise ValueError(f"unknown job: {job_id}")

    bus = get_bus()
    await bus.broadcast({"type": "job_start", "job_id": job_id, "ts": time.time()})

    today_iso = date.today().isoformat()
    started = time.monotonic()
    status = "success"
    detail = ""
    try:
        detail = await handler()
    except Exception as e:
        status = "failed"
        detail = str(e)[:200]
        log.exception(f"[scheduler] job {job_id} failed")
    elapsed_ms = int((time.monotonic() - started) * 1000)

    # 写 task_log (UNIQUE(task_id, date), 用 INSERT OR REPLACE 覆盖当日状态)
    conn = get_connection()
    conn.execute(
        """
        INSERT OR REPLACE INTO task_log (task_id, date, status, completed_at)
        VALUES (?, ?, ?, ?)
        """,
        (job_id, today_iso, status, datetime.now().isoformat(timespec="seconds")),
    )
    conn.commit()

    msg_type = "job_done" if status == "success" else "job_error"
    await bus.broadcast({
        "type": msg_type, "job_id": job_id, "status": status,
        "duration_ms": elapsed_ms, "detail": detail, "ts": time.time(),
    })
    return f"{status} in {elapsed_ms}ms — {detail}"