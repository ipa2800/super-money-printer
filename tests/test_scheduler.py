"""scheduler 烟雾测试 — run_job + task_log 写入 + list_jobs。"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from backend.scheduler import list_jobs
from backend.scheduler.jobs import run_job


def test_list_jobs_seeds(tmp_db):
    """schema 初始化后, refresh_jobs 表应已被 seed 4 行。"""
    jobs = list_jobs()
    assert len(jobs) == 4
    job_ids = {j["job_id"] for j in jobs}
    assert job_ids == {"l0_realtime", "l1_daily", "l2_monthly", "l3_evening"}


def test_run_unknown_job_raises(tmp_db):
    with pytest.raises(ValueError, match="unknown job"):
        asyncio.run(run_job("not_a_real_job"))


def test_run_job_writes_task_log(tmp_db, monkeypatch):
    """mock 一个 handler, 验证 task_log 写入。"""
    from backend.db.connection import get_connection
    from backend.scheduler import jobs as jobs_mod

    async def fake_handler():
        return "wrote 42 rows"

    monkeypatch.setitem(jobs_mod.JOB_HANDLERS, "l3_evening", fake_handler)
    result = asyncio.run(run_job("l3_evening"))
    assert "success" in result
    assert "wrote 42 rows" in result

    conn = get_connection()
    row = conn.execute(
        "SELECT status FROM task_log WHERE task_id='l3_evening' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    assert row["status"] == "success"


def test_run_job_records_failure(tmp_db, monkeypatch):
    from backend.db.connection import get_connection
    from backend.scheduler import jobs as jobs_mod

    async def broken_handler():
        raise RuntimeError("simulated network error")

    monkeypatch.setitem(jobs_mod.JOB_HANDLERS, "l3_evening", broken_handler)
    result = asyncio.run(run_job("l3_evening"))
    assert "failed" in result
    conn = get_connection()
    row = conn.execute(
        "SELECT status FROM task_log WHERE task_id='l3_evening' ORDER BY date DESC LIMIT 1"
    ).fetchone()
    assert row["status"] == "failed"