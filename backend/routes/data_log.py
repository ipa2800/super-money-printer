"""GET /api/data/log?source=&status=&layer=&limit=&offset=  +  DELETE ?before="""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, Query

from backend.db.connection import get_connection
from backend.utils.datalog import cleanup

router = APIRouter(prefix="/api/data/log", tags=["data-log"])


@router.get("")
async def list_log(
    source: str | None = Query(None),
    status: str | None = Query(None),
    layer: str | None = Query(None),
    q: str | None = Query(None, description="关键词模糊搜索 operation/error"),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
) -> dict:
    where: list[str] = []
    params: list = []
    if source:
        where.append("source = ?"); params.append(source)
    if status:
        where.append("status = ?"); params.append(status)
    if layer:
        where.append("layer = ?"); params.append(layer)
    if q:
        where.append("(operation LIKE ? OR error LIKE ?)"); params += [f"%{q}%", f"%{q}%"]
    sql = "SELECT id, ts, layer, source, operation, status, level, latency_ms, rows, error FROM data_log"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY id DESC LIMIT ? OFFSET ?"
    params += [limit, offset]
    conn = get_connection()
    rows = conn.execute(sql, params).fetchall()
    total = conn.execute(
        "SELECT COUNT(*) FROM data_log" + (" WHERE " + " AND ".join(where) if where else ""),
        params[:-2],
    ).fetchone()[0]
    return {"total": total, "items": [dict(r) for r in rows]}


@router.get("/stats")
async def log_stats(hours: int = Query(24, ge=1, le=720)) -> dict:
    """返最近 N 小时分组统计: 每源 成功率 / 平均耗时 / 调用次数."""
    conn = get_connection()
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")
    rows = conn.execute(
        """SELECT source, status, COUNT(*) AS n, AVG(latency_ms) AS avg_ms
           FROM data_log WHERE ts >= ? GROUP BY source, status""",
        (since,),
    ).fetchall()
    sources: dict[str, dict] = {}
    for r in rows:
        s = sources.setdefault(r["source"], {"ok": 0, "fail": 0, "avg_ms": 0})
        key = "ok" if r["status"] == "success" else "fail"
        s[key] += r["n"]   # ponytail: += 而非 =, 同源多 status 行累加
        s["avg_ms"] = round(r["avg_ms"] or 0, 1)
    return {"since": since, "hours": hours, "sources": sources}


@router.delete("")
async def delete_log(before: str = Query(..., description="ISO 时间, 删 ts < before 的")) -> dict:
    """清理旧日志. 例如 before=2026-06-01T00:00:00+00:00"""
    try:
        datetime.fromisoformat(before)
    except ValueError:
        raise HTTPException(status_code=400, detail="before must be ISO 8601 datetime")
    n = cleanup(before)
    return {"deleted": n, "before": before}