"""板块/概念 端点 — snapshot + history + analytics (排名/矩阵)."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, HTTPException, Query

from backend.services.sector_analytics_service import SectorAnalyticsService
from backend.services.sector_service import SectorService

router = APIRouter(prefix="/api/sector", tags=["sector"])


@router.get("/snapshot")
async def get_snapshot() -> dict:
    """返回所有板块/概念的实时快照 (混合 industry+concept, 按 pct_chg 降序)."""
    svc = SectorService()
    try:
        return {"items": await svc.get_snapshot()}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


@router.get("/history")
async def get_history(
    symbol: str = Query(..., description="'industry:BK0473' | 'concept:BKXXXX'"),
    days: int = Query(180, ge=1, le=1000),
    agg: str = Query("day", pattern="^(day|week|month)$"),
) -> dict:
    """返回单个板块/概念的时序."""
    svc = SectorService()
    try:
        return {"symbol": symbol, "rows": await svc.get_history(symbol, days=days, agg=agg)}
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


# ── 板块分析层 (4 维度: 动量+强度 / 资金流 / 涨停密度 / 综合) ──
_SORT_BY = {
    "rank_overall", "rps_20", "accel_5_20", "net_flow_rank", "limit_up_density",
}


@router.get("/analytics/rank")
async def get_rank(
    date_str: str | None = Query(None, alias="date", description="YYYY-MM-DD, 默认今天"),
    sort_by: str = Query("rank_overall", description="rank_overall|rps_20|accel_5_20|net_flow_rank|limit_up_density"),
    limit: int = Query(50, ge=1, le=500),
    sector_type: str | None = Query(None, pattern="^(industry|concept)$"),
) -> dict:
    """返回板块排名 (默认按综合分降序)."""
    svc = SectorAnalyticsService()
    target = date.fromisoformat(date_str) if date_str else date.today()
    if sort_by not in _SORT_BY:
        sort_by = "rank_overall"
    rows = svc.get_rank(target_date=target, sort_by=sort_by, limit=limit, sector_type=sector_type)
    return {"date": target.isoformat(), "sort_by": sort_by, "items": rows}


@router.get("/analytics/matrix")
async def get_matrix(
    date_str: str | None = Query(None, alias="date", description="YYYY-MM-DD, 默认今天"),
) -> dict:
    """返回 4 象限轮动矩阵: 主升浪 / 顶部 / 反弹 / 杀跌."""
    svc = SectorAnalyticsService()
    target = date.fromisoformat(date_str) if date_str else date.today()
    matrix = svc.get_matrix(target_date=target)
    return {"date": target.isoformat(), "matrix": matrix}