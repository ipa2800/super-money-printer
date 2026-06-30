"""自选股端点 — pool CRUD + 单股 kline/fund_flow/summary/news。"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from backend.services.stock_service import StockService

router = APIRouter(prefix="/api/stock", tags=["stock"])
svc = StockService()


@router.get("/list")
async def list_pool() -> dict:
    return {"stocks": StockService.list_pool()}


@router.post("/add")
async def add(code: str = Body(..., embed=True), name: str = Body(None, embed=True)) -> dict:
    StockService.add_to_pool(code=code, name=name)
    return {"ok": True, "code": code}


@router.delete("/{code}")
async def remove(code: str) -> dict:
    n = StockService.remove_from_pool(code)
    return {"ok": True, "deleted": n, "code": code}


@router.get("/search")
async def search(q: str = Query("")) -> dict:
    return {"results": StockService.search(q)}


@router.get("/{code}/kline")
async def kline(
    code: str,
    freq: str = Query("d", pattern="^[dwm]$"),
    limit: int = Query(60, ge=1, le=1000),
) -> dict:
    try:
        rows = await svc.get_kline(code=code, freq=freq, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"code": code, "freq": freq, "count": len(rows), "data": rows}


@router.get("/{code}/fund_flow")
async def fund_flow(code: str) -> dict:
    try:
        rows = StockService.get_fund_flow(code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"code": code, "rows": rows}


@router.get("/{code}/summary")
async def summary(code: str) -> dict:
    try:
        data = StockService.get_summary(code)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    if not data:
        raise HTTPException(status_code=404, detail=f"stock {code} not found")
    return data


@router.get("/{code}/news")
async def news(code: str, limit: int = Query(10, ge=1, le=50)) -> dict:
    try:
        rows = StockService.get_news(code, limit=limit)
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return {"code": code, "count": len(rows), "news": rows}


@router.get("/realtime")
async def realtime_batch(codes: str = Query("", description="comma-separated codes, empty = pool")) -> dict:
    """批量实时报价 (Sina)。空 codes → 拉整个 stock_pool。"""
    if codes.strip():
        code_list = [c.strip() for c in codes.split(",") if c.strip()]
    else:
        code_list = [s["code"] for s in StockService.list_pool()]
    if not code_list:
        return {"as_of": "", "items": {}}
    items = await svc.get_realtime_batch(code_list)
    return {"as_of": next(iter(items.values()), {}).get("time", ""), "items": items}


@router.get("/{code}/minute")
async def minute(code: str) -> dict:
    """分时数据 (Tencent), 240 个 1 分钟 bar。"""
    rows = await svc.get_minute(code)
    if not rows:
        raise HTTPException(status_code=404, detail=f"minute data not available for {code}")
    return {"code": code, "count": len(rows), "data": rows}