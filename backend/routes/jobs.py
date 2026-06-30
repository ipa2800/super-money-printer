"""GET /api/jobs, POST trigger, PATCH cron, GET log — 调度任务完整 CRUD。"""
from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query

from backend.db.connection import get_connection
from backend.scheduler import get_scheduler
from backend.scheduler import list_jobs

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("")
async def get_jobs() -> dict:
    """返回 refresh_jobs 表 + 最近 task_log 状态。"""
    return {"jobs": list_jobs()}


@router.get("/{job_id}/log")
async def get_log(job_id: str, limit: int = Query(10, ge=1, le=100)) -> dict:
    """返最近 N 条 task_log。"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT task_id, date, status, completed_at FROM task_log WHERE task_id = ? ORDER BY date DESC LIMIT ?",
        (job_id, limit),
    ).fetchall()
    return {"job_id": job_id, "logs": [dict(r) for r in rows]}


@router.post("/{job_id}/trigger")
async def trigger_job(job_id: str) -> dict:
    scheduler = get_scheduler()
    try:
        result = await scheduler.trigger(job_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e
    return {"job_id": job_id, "result": result}


@router.patch("/{job_id}")
async def update_job(job_id: str, body: dict = Body(...)) -> dict:
    """改 cron_expr / enabled / description. 不重启 scheduler (下次启动生效)。"""
    conn = get_connection()
    sets: list[str] = []
    params: list = []
    for k in ("cron_expr", "enabled", "description", "retry_cron_expr", "retry_enabled", "retry_max"):
        if k in body:
            sets.append(f"{k} = ?")
            params.append(body[k])
    if not sets:
        raise HTTPException(status_code=400, detail="no updatable fields in body")
    from datetime import datetime, timezone
    sets.append("updated_at = ?")
    params.append(datetime.now(timezone.utc).isoformat(timespec="seconds"))
    params.append(job_id)
    cur = conn.execute(
        f"UPDATE refresh_jobs SET {', '.join(sets)} WHERE job_id = ?", params,
    )
    conn.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail=f"job {job_id} not found")
    return {"ok": True, "job_id": job_id, "updated": cur.rowcount}