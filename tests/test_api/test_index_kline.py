"""/api/index/kline 集成测试 — 真实网络。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client(tmp_db):
    # tmp_db fixture 已建好 schema, 用测试 DB 替换
    with TestClient(app) as c:
        yield c


def test_kline_returns_ohlc(client):
    """真实 baostock 拉 sh.000300 日线 5 条。"""
    r = client.get("/api/index/kline?symbol=sh.000300&freq=d&limit=5")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["symbol"] == "sh.000300"
    assert data["freq"] == "d"
    assert data["count"] >= 1
    row = data["data"][0]
    for col in ("date", "open", "high", "low", "close"):
        assert col in row


def test_kline_rejects_invalid_freq(client):
    r = client.get("/api/index/kline?symbol=sh.000300&freq=invalid&limit=5")
    assert r.status_code == 422  # FastAPI 参数校验


def test_kline_requires_symbol(client):
    r = client.get("/api/index/kline")
    assert r.status_code == 422