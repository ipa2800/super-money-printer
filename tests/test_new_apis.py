"""新增端点测试 — /api/index/add|remove, data, /api/etf/data, /api/macro/data|ranges, /api/jobs PATCH|log。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_db):
    from backend.main import app
    with TestClient(app) as c:
        yield c


def test_index_add_and_remove(client):
    r = client.post("/api/index/add", json={"symbol": "sh.000300", "name": "沪深300"})
    assert r.status_code == 200
    r = client.get("/api/index/pool/list")
    assert any(p["symbol"] == "sh.000300" for p in r.json()["indexes"])
    r = client.delete("/api/index/remove", params={"symbol": "sh.000300"})
    assert r.status_code == 200
    assert r.json()["deleted_pool"] == 1


def test_etf_data_with_agg(client):
    """days + agg 参数, 默认 agg=day."""
    r = client.get("/api/etf/data?days=30&agg=day")
    assert r.status_code == 200
    body = r.json()
    assert body["agg"] == "day"
    assert body["days"] == 30
    assert "shares_timeseries" in body


def test_macro_data(client):
    r = client.get("/api/macro/data?indicator=mainflow&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["indicator"] == "mainflow"


def test_macro_ranges(client):
    r = client.get("/api/macro/ranges")
    assert r.status_code == 200
    assert "indicators" in r.json()


def test_jobs_log_empty(client):
    r = client.get("/api/jobs/l3_evening/log")
    assert r.status_code == 200
    assert r.json()["job_id"] == "l3_evening"


def test_jobs_patch_cron(client):
    r = client.patch("/api/jobs/l0_realtime", json={"cron_expr": "5 * * * *"})
    assert r.status_code == 200
    assert r.json()["ok"]
    # 验证真的更新了
    r = client.get("/api/jobs")
    job = next(j for j in r.json()["jobs"] if j["job_id"] == "l0_realtime")
    assert job["cron_expr"] == "5 * * * *"
    # 改回去
    client.patch("/api/jobs/l0_realtime", json={"cron_expr": "0 * * * *"})


def test_jobs_patch_unknown_job_404(client):
    r = client.patch("/api/jobs/not_a_real_job", json={"cron_expr": "0 * * * *"})
    assert r.status_code == 404


def test_status_failed_when_provider_sick(tmp_db):
    """手动塞一个 error_count >= 5 的 provider_health 行, 验证 status=failed。"""
    cur = tmp_db.cursor()
    # 加 error_count 列(IF NOT EXISTS 不支持, 用 try/except)
    try:
        cur.execute("ALTER TABLE provider_health ADD COLUMN error_count INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass
    cur.execute(
        "INSERT OR REPLACE INTO provider_health (provider, status, last_check, error_count) VALUES (?, ?, ?, ?)",
        ("akshare", "degraded", "2026-06-30T00:00:00", 7),
    )
    cur.execute(
        "INSERT INTO macro_cache (indicator, date, value, source, fetched_at) VALUES (?,?,?,?,?)",
        ("mainflow", "2026-06-29", 1.0, "test", "2026-06-29T22:00:00"),
    )
    tmp_db.commit()
    from backend.services.cache_service import CacheService
    items = CacheService.get_status()["items"]
    mainflow = next(i for i in items if i["key"] == "mainflow")
    assert mainflow["status"] == "failed"