"""SQLite connection helper — WAL 模式 + 单例 + 行字典工厂。"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional

from backend.config import get_settings


_connection: Optional[sqlite3.Connection] = None


def get_connection() -> sqlite3.Connection:
    """获取全局 SQLite 连接 (WAL 模式, Row 工厂)。"""
    global _connection
    if _connection is None:
        settings = get_settings()
        db_path: Path = settings.db_path_resolved
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _connection = sqlite3.connect(
            str(db_path),
            detect_types=sqlite3.PARSE_DECLTYPES,
            check_same_thread=False,  # ponytail: FastAPI 单进程多线程,后续换连接池时改
            isolation_level=None,  # autocommit,事务显式 BEGIN/COMMIT
        )
        _connection.row_factory = sqlite3.Row
        # WAL: 多读单写并发友好
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA synchronous=NORMAL")
        _connection.execute("PRAGMA foreign_keys=ON")
    return _connection


def reset_connection() -> None:
    """测试用 — 关闭并清空全局连接。"""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None