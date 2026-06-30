"""AsyncIOScheduler wrapper — 读 refresh_jobs 表注册 cron, lifespan 启动/关停。"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from backend.db.connection import get_connection

log = logging.getLogger(__name__)


def list_jobs() -> list[dict]:
    """从 refresh_jobs 读全部 job + 最近一次 task_log 状态。"""
    conn = get_connection()
    jobs = [dict(r) for r in conn.execute(
        "SELECT * FROM refresh_jobs ORDER BY id"
    ).fetchall()]
    # join 最近 task_log
    for j in jobs:
        last = conn.execute(
            "SELECT status, completed_at FROM task_log WHERE task_id = ? ORDER BY date DESC LIMIT 1",
            (j["job_id"],),
        ).fetchone()
        if last:
            j["last_status"] = last["status"]
            j["last_run_at"] = last["completed_at"]
        else:
            j["last_status"] = None
            j["last_run_at"] = None
    return jobs


class AppScheduler:
    """包装 AsyncIOScheduler, 启动时读 refresh_jobs 注册 cron。"""

    def __init__(self) -> None:
        self.sched: Optional[AsyncIOScheduler] = None
        # job_id → APScheduler job (用于 trigger_job)
        self._registered: dict[str, object] = {}

    def start(self) -> None:
        from backend.scheduler.jobs import run_job
        self.sched = AsyncIOScheduler(timezone="Asia/Shanghai")
        for j in list_jobs():
            if not j["enabled"]:
                continue
            try:
                trigger = CronTrigger.from_crontab(j["cron_expr"], timezone="Asia/Shanghai")
            except Exception as e:
                log.warning(f"[scheduler] skip {j['job_id']} bad cron {j['cron_expr']!r}: {e}")
                continue
            self._registered[j["job_id"]] = self.sched.add_job(
                run_job, trigger=trigger, args=[j["job_id"]],
                id=j["job_id"], name=j["description"], replace_existing=True,
            )
            log.info(f"[scheduler] registered {j['job_id']} cron='{j['cron_expr']}'")
        self.sched.start()

    async def trigger(self, job_id: str) -> str:
        """手动触发一个 job, 同步跑完返回结果。"""
        from backend.scheduler.jobs import run_job
        return await run_job(job_id)

    async def shutdown(self) -> None:
        if self.sched and self.sched.running:
            self.sched.shutdown(wait=False)
            log.info("[scheduler] shutdown")


# 全局单例
_scheduler: Optional[AppScheduler] = None


def get_scheduler() -> AppScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AppScheduler()
    return _scheduler


def reset_scheduler() -> None:
    global _scheduler
    _scheduler = None