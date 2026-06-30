"""CacheService 烟雾 — status 形状, ranges, clear。"""
from __future__ import annotations

import pytest


def test_status_empty_db(tmp_db):
    from backend.services.cache_service import CacheService
    out = CacheService.get_status()
    assert out["now"]
    assert out["items"] == []


def test_status_after_macro_insert(tmp_db):
    from datetime import datetime, timezone
    from backend.services.cache_service import CacheService
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = tmp_db.cursor()
    cur.execute(
        "INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
        ("mainflow", "2026-06-29", 123.4, "test", now_iso),
    )
    tmp_db.commit()
    out = CacheService.get_status()
    assert any(it["key"] == "mainflow" for it in out["items"])
    item = next(it for it in out["items"] if it["key"] == "mainflow")
    assert item["status"] == "success"
    assert item["ttl_seconds"] == 25 * 3600


def test_status_stale(tmp_db):
    from datetime import datetime, timedelta, timezone
    from backend.services.cache_service import CacheService
    old = (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(timespec="seconds")
    cur = tmp_db.cursor()
    cur.execute(
        "INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
        ("mainflow", "2026-06-27", 50.0, "test", old),
    )
    tmp_db.commit()
    out = CacheService.get_status()
    item = next(it for it in out["items"] if it["key"] == "mainflow")
    assert item["status"] == "stale"


def test_ranges_shape(tmp_db):
    from backend.services.cache_service import CacheService
    out = CacheService.get_ranges()
    # realtime_cache 总是有 (count=0), 其他表只在有行时出现
    assert "realtime_cache" in out
    assert out["realtime_cache"] == {"ALL": {"count": 0}}


def test_clear_scope(tmp_db):
    from datetime import datetime, timezone
    cur = tmp_db.cursor()
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur.execute(
        "INSERT INTO shares_cache (code, date, shares, source, fetched_at) VALUES (?,?,?,?,?)",
        ("510300", "2026-06-29", 1e9, "test", now),
    )
    cur.execute(
        "INSERT INTO shares_cache (code, date, shares, source, fetched_at) VALUES (?,?,?,?,?)",
        ("510500", "2026-06-29", 1e9, "test", now),
    )
    tmp_db.commit()
    from backend.services.cache_service import CacheService
    n = CacheService.clear(scope="shares", key="510300")
    assert n == 1
    rows = tmp_db.execute("SELECT code FROM shares_cache").fetchall()
    assert {r["code"] for r in rows} == {"510500"}


def test_clear_unknown_scope_raises(tmp_db):
    from backend.services.cache_service import CacheService
    with pytest.raises(ValueError, match="unknown scope"):
        CacheService.clear(scope="garbage")