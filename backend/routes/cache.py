"""Cache 管理端点 — status / ranges / refresh / backfill / clear。"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Body, HTTPException, Query

from backend.db.connection import get_connection
from backend.scheduler.jobs import run_job
from backend.services.cache_service import CacheService

router = APIRouter(prefix="/api/cache", tags=["cache"])


@router.get("/status")
async def get_status() -> dict:
    return CacheService.get_status()


@router.get("/ranges")
async def get_ranges() -> dict:
    return CacheService.get_ranges()


@router.post("/refresh")
async def refresh(job_id: Optional[str] = Body(None, embed=True)) -> dict:
    """body: {job_id?}. 省略 job_id = 全跑 l0/l1/l3。"""
    try:
        result = await CacheService.refresh(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"result": result}


@router.post("/backfill")
async def backfill(
    symbol: str = Body(..., embed=True),
    freq: str = Body("d", embed=True),
    days: int = Body(365, embed=True),
) -> dict:
    try:
        result = await CacheService.backfill_kline(symbol=symbol, freq=freq, days=days)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return result


@router.post("/clear")
async def clear(scope: str = Body(..., embed=True), key: Optional[str] = Body(None, embed=True)) -> dict:
    try:
        n = CacheService.clear(scope=scope, key=key)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"deleted": n}


# ── macro / index 别名端点, 方便前端分别调 ──────────────────
@router.post("/macro/refresh")
async def macro_refresh() -> dict:
    return {"result": await run_job("l3_evening")}


@router.post("/macro/backfill")
async def macro_backfill(indicator: str = Body(..., embed=True), years: int = Body(2, embed=True)) -> dict:
    from backend.providers.registry import get_registry
    from backend.services.macro_service import CARD_DEFS
    def_ = next((d for d in CARD_DEFS if d["indicator"] == indicator or d["indicator"].replace("_1y", "") == indicator), None)
    if not def_:
        raise HTTPException(status_code=400, detail=f"unknown indicator: {indicator}")
    end = date.today()
    start = end.replace(year=end.year - years)
    registry = get_registry()
    try:
        results = await registry.fetch_with_fallback(indicator, start, end)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    if not results:
        return {"indicator": indicator, "n_written": 0}
    conn = get_connection()
    cur = conn.cursor()
    now_iso = results[0].fetched_at.isoformat(timespec="seconds")
    n = 0
    for r in results:
        if r.value is None:
            continue
        cur.execute(
            """INSERT OR REPLACE INTO macro_cache (indicator, date, value, source, fetched_at)
               VALUES (?, ?, ?, ?, ?)""",
            (indicator, r.date.isoformat(), float(r.value), r.source, now_iso),
        )
        n += 1
    conn.commit()
    return {"indicator": indicator, "n_written": n}


@router.post("/index/refresh")
async def index_refresh(symbol: str = Body(..., embed=True)) -> dict:
    from backend.services.index_service import IndexService
    svc = IndexService()
    rows = await svc.get_kline(symbol=symbol, freq="d", limit=60)
    return {"symbol": symbol, "count": len(rows)}


@router.post("/index/backfill")
async def index_backfill(
    symbol: str = Body(..., embed=True),
    freq: str = Body("d", embed=True),
    start_date: str = Body(..., embed=True),
    end_date: str = Body(..., embed=True),
) -> dict:
    from backend.services.index_service import IndexService
    try:
        sd = date.fromisoformat(start_date)
        ed = date.fromisoformat(end_date)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    svc = IndexService()
    try:
        n = await svc.backfill(symbol=symbol, freq=freq, start_date=sd, end_date=ed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"symbol": symbol, "freq": freq, "n_written": n}