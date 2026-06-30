"""Alerts endpoints — config + list + ack + run-checks。"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from backend.services.alert_service import AlertService

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.get("")
async def list_alerts(limit: int = 50, only_unack: bool = False) -> dict:
    return {"alerts": AlertService.list_alerts(limit=limit, only_unack=only_unack)}


@router.get("/summary")
async def summary(limit: int = 3) -> dict:
    """dashboard 顶部 alert 摘要 — 最新 N 条 + 红黄计数。"""
    alerts = AlertService.list_alerts(limit=limit, only_unack=True)
    red = sum(1 for a in alerts if a["severity"] == "red")
    yellow = sum(1 for a in alerts if a["severity"] == "yellow")
    return {"red": red, "yellow": yellow, "top": alerts[:3]}


@router.post("/check")
async def run_checks() -> dict:
    """手动触发一次全量阈值检查。"""
    svc = AlertService()
    return await svc.run_all_checks()


@router.post("/{alert_id}/ack")
async def ack(alert_id: int) -> dict:
    if not AlertService.ack(alert_id):
        raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
    return {"ok": True, "alert_id": alert_id}


# /api/config/alerts — 在 main.py 单挂, 这里不重复
def get_config() -> dict:
    return AlertService.get_config()