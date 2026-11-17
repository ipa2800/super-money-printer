"""Scheduler jobs — 每个 layer 一个 async 函数, 失败写 task_log。"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta

from backend.db.connection import get_connection
from backend.providers.registry import get_registry
from backend.providers.base import FetchResult, KLineFreq
from backend.services.etf_service import ETFService
from backend.services.index_service import IndexService
from backend.services.stock_service import StockService

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


async def _fetch_kline_one(symbol: str, days_back: int = 60) -> list[FetchResult]:
    """单 symbol kline 拉取 (baostock / akshare_etf_kline), 出错返回 []。"""
    registry = get_registry()
    date_to = date.today()
    date_from = date_to - timedelta(days=days_back)
    try:
        return await registry.fetch_with_fallback(
            "kline", date_from, date_to, freq=KLineFreq.DAILY, symbol=symbol,
        )
    except Exception as e:
        log.warning(f"[scheduler] kline {symbol} failed: {e}")
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


def _write_shares(results: list[FetchResult], pool_codes: set[str] | None = None) -> int:
    """写 shares_cache。

    ponytail: SSE/SZSE 整批 17371 行; 只保留 pool 内的 code, 否则 shares_cache 月增 30k+ 无意义行 (cache bloat 根因)。
    pool_codes=None 表示不限 (e.g. 测试场景)。
    """
    if not results:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    now_iso = results[0].fetched_at.isoformat(timespec="seconds")
    n = 0
    for r in results:
        if r.value is None or r.symbol is None:
            continue
        if pool_codes is not None and r.symbol not in pool_codes:
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


def _write_kline(results: list[FetchResult]) -> int:
    """写 kline_cache (ETF/指数/股票 统一, symbol 自动区分)。"""
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
             r.source, now_iso),
        )
        n += 1
    conn.commit()
    return n


def _write_volume(results: list[FetchResult], pool_codes: set[str]) -> int:
    """写 volume_cache, 只接 pool 内 code (纯数字 6 位不带 sh./sz. 前缀)。

    ponytail: kline fetch 已含 volume 字段, 直接从 fields 提一份写 volume_cache — 不重复网络请求。
    symbol 来源可能是 'sh510300' (akshare) / 'sh.510300' (baostock 兼容) — 两种都剥成 '510300' 比 pool。
    """
    if not results:
        return 0
    conn = get_connection()
    cur = conn.cursor()
    now_iso = results[0].fetched_at.isoformat(timespec="seconds")
    n = 0
    for r in results:
        if r.symbol is None:
            continue
        # 剥掉 sh./sz. 或 sh/sz 前缀, 留 6 位数字
        bare = r.symbol.split(".")[-1]
        if bare.startswith(("sh", "sz")) and len(bare) > 2:
            bare = bare[2:]
        if bare not in pool_codes:
            continue
        vol = (r.fields or {}).get("volume")
        if vol is None:
            continue
        cur.execute(
            "INSERT OR REPLACE INTO volume_cache (code, date, volume, source, fetched_at) VALUES (?,?,?,?,?)",
            (bare, r.date.isoformat(), float(vol), r.source, now_iso),
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


# ── L1 日终: ETF 份额 + K线封存 + 成交量 (16:05) ─────────────────────
async def job_l1_daily() -> str:
    """日终结算:
    1. ETF 份额 (SSE/SZSE, 只写 pool)
    2. K线封存: ETF pool + Index pool + Stock pool (来自 baostock kline 拉取)
    3. ETF 成交量 (从 K线结果的 volume 字段写 volume_cache, 只保留 ETF pool)
    4. ETF 实时行情复盘
    """
    log.info("[L1] daily start")

    # 池子快照 — 提前读, 整批用
    etf_pool = ETFService().list_pool()
    idx_pool = IndexService.list_pool()
    stock_pool = StockService.list_pool()
    etf_codes = {e["code"] for e in etf_pool}
    summary: dict[str, int] = {}

    # 1. ETF 份额
    shares_results = await _fetch_one("etf_shares", days_back=30)
    summary["shares"] = _write_shares(shares_results, pool_codes=etf_codes)

    # 2. K线封存 — ETF 走 akshare sh 格式 (e.g. sh510300); 指数/股票用 baostock 格式 (e.g. sh.000300)
    n_kline_etf = n_kline_idx = n_kline_stock = n_vol = 0
    days_back = 60  # 拉 60 天覆盖 sparkline

    for e in etf_pool:
        sym = e["code"] if "." in e["code"] else f"sh{e['code']}"  # 510xxx → sh510xxx for akshare
        rs = await _fetch_kline_one(sym, days_back=days_back)
        n_kline_etf += _write_kline(rs)
        n_vol += _write_volume(rs, etf_codes)

    for ix in idx_pool:
        rs = await _fetch_kline_one(ix["symbol"], days_back=days_back)
        n_kline_idx += _write_kline(rs)

    for st in stock_pool:
        # 6xxxxx → 上海 (sh.), 其余 → 深圳 (sz.)。baostock 格式必须带前缀
        sym = st["code"] if "." in st["code"] else (
            f"sh.{st['code']}" if st["code"].startswith("6") else f"sz.{st['code']}"
        )
        rs = await _fetch_kline_one(sym, days_back=days_back)
        n_kline_stock += _write_kline(rs)

    summary["kline_etf"] = n_kline_etf
    summary["kline_idx"] = n_kline_idx
    summary["kline_stock"] = n_kline_stock
    summary["volume"] = n_vol

    # 4. ETF 实时行情复盘 (16:05 后用盘后数据, 否则跳过也无所谓 — l0 每分钟也会写)
    rt_results = await _fetch_one("etf_realtime", days_back=1)
    summary["realtime"] = _write_realtime(rt_results)

    log.info(f"[L1] daily done: {summary}")
    return ", ".join(f"{k}={v}" for k, v in summary.items())


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


# ── L4 板块/概念: 启动时 snapshot + 02:30 全量历史 ──────────────────
async def job_l4_sector() -> str:
    """板块/概念: 刷新快照 + 全量历史 (隔夜跑, ~380 boards × 0.3s ≈ 2 min)."""
    log.info("[L4] sector start")
    from backend.services.sector_service import SectorService
    svc = SectorService()

    n_snap = await svc.refresh_snapshot()
    if n_snap == 0:
        return "snapshot fetch failed"

    # 全量历史 (cache 里现有的所有 code+type)
    ok = await svc.refresh_all_history(delay_sec=0.3)
    log.info(f"[L4] sector done: snapshot={n_snap} history={ok}")
    return f"snapshot={n_snap} history={ok}"


# ── L5 板块分析: 收市后算 RPS/资金流/涨停密度 (工作日 16:30) ─────────
async def job_l5_sector_analytics() -> str:
    """板块分析: 拉资金流 + 成分股 + 涨停池, 算指标写 sector_analytics.
    跑完后调用 alert 规则 (主升浪/资金异常/龙头确立) 推到 alert 中心."""
    log.info("[L5] sector_analytics start")
    from backend.services.sector_analytics_service import SectorAnalyticsService
    svc = SectorAnalyticsService()
    summary = await svc.refresh_all()
    log.info(f"[L5] sector_analytics refresh done: {summary}")

    # 跑 alert 规则
    try:
        from backend.services.alert_service import AlertService
        await AlertService().run_sector_rules()
    except Exception as e:
        log.warning(f"[L5] alert rules failed: {e}")

    return f"fund_flow={summary['fund_flow']} cons={summary['constituents_industry']}/{summary['constituents_concept']} lup={summary['limit_up_pool']} analytics={summary['analytics']}"


# ── Job → handler 映射 ───────────────────────────────────────────────
JOB_HANDLERS = {
    "l0_realtime": job_l0_realtime,
    "l1_daily":    job_l1_daily,
    "l2_monthly":  job_l2_monthly,
    "l3_evening":  job_l3_evening,
    "l4_sector":   job_l4_sector,
    "l5_sector_analytics": job_l5_sector_analytics,
}


# ponytail: data_log 自动清理 — 每天 03:15 跑, 删 30 天前. 不进 refresh_jobs (内部维护, 不需要用户触发)
async def job_cleanup_data_log() -> str:
    from datetime import datetime, timedelta, timezone
    from backend.utils.datalog import cleanup
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat(timespec="seconds")
    n = cleanup(cutoff)
    log.info(f"[cleanup] data_log removed {n} rows older than {cutoff}")
    return f"removed {n} rows"


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
    # ponytail: 写 data_log (job 层, 与 task_log 并存 — task_log 给 JobList, data_log 给详细分析)
    from backend.utils.datalog import log_job
    log_job(job_id, status == "success", detail, elapsed_ms)

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