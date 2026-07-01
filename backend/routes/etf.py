"""ETF 端点 — overview + pool CRUD + 搜索。"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from backend.services.etf_service import ETFService

router = APIRouter(prefix="/api/etf", tags=["etf"])


@router.get("/overview")
async def get_overview(
    days: int = Query(30, ge=1, le=1000),
    agg: str = Query("day", pattern="^(day|week|month)$"),
) -> dict:
    svc = ETFService()
    try:
        return await svc.get_overview(days=days, agg=agg)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/list")
async def list_pool() -> dict:
    svc = ETFService()
    return {"etfs": svc.list_pool()}


@router.post("/add")
async def add(code: str = Body(..., embed=True), name: str = Body(None, embed=True)) -> dict:
    ETFService.add_to_pool(code=code, name=name)
    return {"ok": True, "code": code}


@router.delete("/{code}")
async def remove(code: str) -> dict:
    n = ETFService.remove_from_pool(code)
    return {"ok": True, "deleted": n, "code": code}


@router.get("/search")
async def search(q: str = Query("")) -> dict:
    svc = ETFService()
    try:
        results = await svc.search(q)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"results": results}


# spec §6.1: /api/etf/data?days=N&agg=day|week|month
@router.get("/data")
async def get_data(
    days: int = Query(20, ge=1, le=1000),
    agg: str = Query("day", pattern="^(day|week|month)$"),
    cache_only: bool = Query(False, description="只从DB读, 不发网络请求"),
) -> dict:
    """返回 ETF 池 + 份额时序 (按 agg 聚合) + 实时行情。"""
    svc = ETFService()
    try:
        return await svc.get_data(days=days, agg=agg, cache_only=cache_only)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e