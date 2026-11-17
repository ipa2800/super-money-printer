"""数据日志 — provider fetch / scheduler job 双层追踪。ponytail: sync INSERT, 写表本身是轻量操作."""
from __future__ import annotations

import time
from contextlib import contextmanager
from datetime import datetime, timezone

from backend.db.connection import get_connection

_MAX_ERR = 500


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _insert(layer: str, source: str, op: str, status: str, level: str,
            latency_ms: int | None, rows: int | None, error: str | None) -> None:
    try:
        get_connection().execute(
            """INSERT INTO data_log
               (ts, layer, source, operation, status, level, latency_ms, rows, error)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (_now_iso(), layer, source, op, status, level, latency_ms, rows, error),
        )
        get_connection().commit()
    except Exception:
        # ponytail: 日志写失败不能阻塞业务调用
        pass


def log_call(layer: str, source: str, op: str = ""):
    """装饰器/上下文管理器: 包一次调用, 记耗时+状态. 用法:

        with log_call("provider", "akshare", "fetch:etf_realtime"):
            results = await ...

    ponytail: provider 层自动加 'provider:' 前缀, 与 'job:' 视觉对齐
    """
    if layer == "provider" and not source.startswith("provider:"):
        source = f"provider:{source}"
    return _LogCtx(layer, source, op)


@contextmanager
def _LogCtx(layer: str, source: str, op: str):
    t0 = time.monotonic()
    err: str | None = None
    state = _LogState()
    try:
        yield state
        status, level = "success", "info"
    except Exception as e:
        status, level = "fail", "error"
        err = str(e)[:_MAX_ERR]
        raise
    finally:
        ms = int((time.monotonic() - t0) * 1000)
        _insert(layer, source, op, status, level, ms, state.rows, err)


class _LogState:
    """ctx 内部用: 让业务设置 rows 计数."""
    def __init__(self) -> None:
        self.rows: int | None = None
    def set_rows(self, n: int) -> None:
        self.rows = n


# ponytail: 提供非装饰器版, 给 scheduler job 用 (job 已有 try/except, 这里只 wrap)
def log_job(job_id: str, ok: bool, detail: str = "", latency_ms: int = 0) -> None:
    _insert(
        layer="job",
        source=f"job:{job_id}",
        op=job_id,
        status="success" if ok else "fail",
        level="info" if ok else "error",
        latency_ms=latency_ms,
        rows=None,
        error=None if ok else detail[:_MAX_ERR],
    )


def log_fail(layer: str, source: str, op: str, error: str, latency_ms: int = 0) -> None:
    """一次性记一条失败 (不进 with 块时用)."""
    _insert(layer, source, op, "fail", "error", latency_ms, None, error[:_MAX_ERR])


def cleanup(before_iso: str) -> int:
    """删 ts < before_iso 的旧行. 返 deleted count."""
    cur = get_connection().execute("DELETE FROM data_log WHERE ts < ?", (before_iso,))
    get_connection().commit()
    return cur.rowcount