"""GET /api/macro/cards + /api/macro/data + /api/macro/ranges。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from backend.db.connection import get_connection
from backend.services.macro_service import MacroService

router = APIRouter(prefix="/api/macro", tags=["macro"])


@router.get("/cards")
async def get_cards() -> dict:
    svc = MacroService()
    try:
        return await svc.get_cards()
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e)) from e


# spec §6.1: /api/macro/data?indicator=&from=&to=  返时间序列行
@router.get("/data")
async def get_data(
    indicator: str = Query(...),
    date_from: str | None = Query(None, description="YYYY-MM-DD"),
    date_to: str | None = Query(None, description="YYYY-MM-DD"),
    limit: int = Query(365, ge=1, le=10000),
) -> dict:
    conn = get_connection()
    if date_from and date_to:
        rows = conn.execute(
            "SELECT date, value, source FROM macro_cache WHERE indicator = ? AND date BETWEEN ? AND ? ORDER BY date",
            (indicator, date_from, date_to),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT date, value, source FROM macro_cache WHERE indicator = ? ORDER BY date DESC LIMIT ?",
            (indicator, limit),
        ).fetchall()
        rows = list(reversed(rows))
    return {"indicator": indicator, "count": len(rows),
            "data": [{"date": r["date"], "value": r["value"], "source": r["source"]} for r in rows]}


# spec §6.1: /api/macro/ranges — 每个 indicator 的 min/max date + 行数
@router.get("/ranges")
async def get_ranges() -> dict:
    conn = get_connection()
    rows = conn.execute(
        """SELECT indicator, MIN(date) AS min_date, MAX(date) AS max_date, COUNT(*) AS n
           FROM macro_cache GROUP BY indicator ORDER BY indicator"""
    ).fetchall()
    return {"indicators": [dict(r) for r in rows]}