"""alert_service 烟雾测试 — 用 seed 数据触发阈值检查。"""
from __future__ import annotations

from datetime import date

import pytest

from backend.db.connection import get_connection
from backend.services.alert_service import AlertService


@pytest.fixture
def seeded_db(tmp_db):
    """种入超阈值的 macro 行 — bond_10y 单日变化 0.15 (> 0.10 阈值)。"""
    conn = get_connection()
    cur = conn.cursor()
    # bond_10y: 1.6 → 1.75  变化 0.15 > warn
    cur.execute("INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
                ("bond_10y", "2026-06-26", 1.60, "test", "2026-06-26T10:00:00"))
    cur.execute("INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
                ("bond_10y", "2026-06-29", 1.75, "test", "2026-06-29T10:00:00"))
    # mainflow: 0 → 2500  变化 2500 > critical 2000
    cur.execute("INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
                ("mainflow", "2026-06-26", 0.0, "test", "2026-06-26T10:00:00"))
    cur.execute("INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
                ("mainflow", "2026-06-29", 2500.0, "test", "2026-06-29T10:00:00"))
    # m2: 平稳
    cur.execute("INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
                ("m2", "2026-05-01", 8.0, "test", "2026-05-01T10:00:00"))
    cur.execute("INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
                ("m2", "2026-06-01", 8.2, "test", "2026-06-01T10:00:00"))
    conn.commit()
    return conn


def test_macro_check_triggers_alerts(seeded_db):
    svc = AlertService()
    n = svc.check_macro()
    assert n == 2  # bond_10y yellow + mainflow red
    alerts = svc.list_alerts(only_unack=False)
    by_source = {a["source"]: a for a in alerts}
    assert by_source["bond_10y"]["severity"] == "yellow"
    assert by_source["mainflow"]["severity"] == "red"


def test_alert_ack_works(seeded_db):
    svc = AlertService()
    svc.check_macro()
    alerts = svc.list_alerts()
    assert alerts[0]["acknowledged"] == 0
    aid = alerts[0]["id"]
    AlertService.ack(aid)
    # re-query — sqlite3 rows aren't live objects
    refreshed = [a for a in svc.list_alerts() if a["id"] == aid][0]
    assert refreshed["acknowledged"] == 1


def test_get_config_returns_thresholds():
    cfg = AlertService.get_config()
    assert "macro" in cfg
    assert "etf_share_daily_change" in cfg
    assert cfg["macro"]["bond_10y"]["warn"] == 0.10


def test_check_macro_empty_db(tmp_db):
    svc = AlertService()
    n = svc.check_macro()
    assert n == 0