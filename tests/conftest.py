"""pytest 配置 + fixtures。"""
from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture
def tmp_db_path(tmp_path, monkeypatch):
    """测试用独立 SQLite 文件,不污染真实 db。"""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    # 清空 settings cache + connection 单例
    from backend.config import get_settings
    from backend.db import connection as conn_mod
    get_settings.cache_clear()
    conn_mod.reset_connection()
    yield db_path
    conn_mod.reset_connection()
    get_settings.cache_clear()


@pytest.fixture
def tmp_db(tmp_db_path):
    """建好 schema 的空 db。"""
    from backend.db.connection import get_connection
    from backend.db.schema import init_schema
    conn = get_connection()
    init_schema(conn)
    return conn