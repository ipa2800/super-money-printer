"""Routes 烟雾 — cache/stocks/etf/index pool 端点形状。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_db):
    from backend.main import app
    with TestClient(app) as c:
        yield c


def test_etf_list_default(client):
    r = client.get("/api/etf/list")
    assert r.status_code == 200
    assert len(r.json()["etfs"]) == 4


def test_etf_add_remove(client):
    r = client.post("/api/etf/add", json={"code": "510500", "name": "中证500"})
    assert r.status_code == 200
    r = client.get("/api/etf/list")
    assert "510500" in [e["code"] for e in r.json()["etfs"]]
    r = client.delete("/api/etf/510500")
    assert r.status_code == 200
    assert r.json()["deleted"] == 1


def test_index_pool_crud(client):
    r = client.post("/api/index/pool/add", json={"symbol": "sh.000300", "name": "沪深300"})
    assert r.status_code == 200
    r = client.get("/api/index/pool/list")
    assert any(p["symbol"] == "sh.000300" for p in r.json()["indexes"])
    r = client.post("/api/index/pool/remove", json={"symbol": "sh.000300"})
    assert r.json()["deleted"] == 1


def test_stock_pool_crud(client):
    r = client.post("/api/stock/add", json={"code": "000001", "name": "平安银行"})
    assert r.status_code == 200
    r = client.get("/api/stock/list")
    assert any(s["code"] == "000001" for s in r.json()["stocks"])
    r = client.delete("/api/stock/000001")
    assert r.json()["deleted"] == 1


def test_cache_status_shape(client):
    r = client.get("/api/cache/status")
    assert r.status_code == 200
    body = r.json()
    assert "now" in body and "items" in body


def test_cache_clear(client):
    r = client.post("/api/cache/clear", json={"scope": "macro", "key": "mainflow"})
    assert r.status_code == 200
    assert "deleted" in r.json()


def test_cache_clear_bad_scope_400(client):
    r = client.post("/api/cache/clear", json={"scope": "garbage"})
    assert r.status_code == 400


def test_stock_summary_unknown_code_404(client):
    r = client.get("/api/stock/999999/summary")
    assert r.status_code in (404, 502)  # 网络失败也是 502