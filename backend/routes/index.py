"""指数端点 — kline + pool CRUD + cache list (spec URL: /api/index/add /remove)。"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from backend.services.index_service import IndexService

router = APIRouter(prefix="/api/index", tags=["index"])


@router.get("/kline")
async def get_kline(
    symbol: str = Query(..., description="指数代码, baostock 格式, 如 sh.000300"),
    freq: str = Query("d", pattern="^[dwm]$", description="d/w/m"),
    limit: int = Query(60, ge=1, le=1000),
) -> dict:
    svc = IndexService()
    try:
        rows = await svc.get_kline(symbol=symbol, freq=freq, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {
        "symbol": symbol,
        "freq": freq,
        "count": len(rows),
        "data": rows,
    }


@router.get("/cache/list")
async def cache_list() -> dict:
    return {"indexes": IndexService.list_cached_symbols()}


@router.get("/pool/list")
async def pool_list() -> dict:
    return {"indexes": IndexService.list_pool()}


# spec §6.1 规定 URL: POST /api/index/add + DELETE /api/index/remove
@router.post("/add")
async def add(symbol: str = Body(..., embed=True), name: str = Body(None, embed=True)) -> dict:
    """加入指数池 + 触发一次 60 天回填 (UI 后续会调 cache/backfill 拉更久)。"""
    IndexService.add_to_pool(symbol=symbol, name=name)
    return {"ok": True, "symbol": symbol}


@router.delete("/remove")
async def remove(symbol: str = Query(..., description="指数代码")) -> dict:
    """从 kline_cache 删除 + 从 index_pool 移除。"""
    n_cache = IndexService.remove_from_cache(symbol)
    n_pool = IndexService.remove_from_pool(symbol)
    return {"ok": True, "deleted_cache": n_cache, "deleted_pool": n_pool, "symbol": symbol}


# 内部别名, 保持向后兼容
@router.post("/pool/add")
async def pool_add(symbol: str = Body(..., embed=True), name: str = Body(None, embed=True)) -> dict:
    return await add(symbol=symbol, name=name)


@router.post("/pool/remove")
async def pool_remove(symbol: str = Body(..., embed=True)) -> dict:
    IndexService.remove_from_pool(symbol)
    return {"ok": True, "deleted": 1, "symbol": symbol}


@router.post("/cache/remove")
async def cache_remove(symbol: str = Body(..., embed=True)) -> dict:
    n = IndexService.remove_from_cache(symbol)
    return {"ok": True, "deleted": n, "symbol": symbol}


# spec §6.1: /api/index/data?days=N&agg=day|week|month
@router.get("/data")
async def get_data(
    symbol: str = Query(..., description="指数代码, baostock 格式"),
    days: int = Query(20, ge=1, le=1000),
    agg: str = Query("day", pattern="^(day|week|month)$"),
) -> dict:
    svc = IndexService()
    try:
        rows = await svc.get_data(days=days, agg=agg, symbol=symbol)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"symbol": symbol, "days": days, "agg": agg, "count": len(rows), "data": rows}