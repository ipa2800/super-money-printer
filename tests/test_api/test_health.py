"""/api/health 集成测试。"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.main import app


@pytest.fixture
def client():
    # TestClient 进入 lifespan, 触发 registry.bootstrap() (含 baostock.login())
    with TestClient(app) as c:
        yield c


def test_health_returns_200_and_registry(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert data["ok"] is True
    assert "registry" in data
    assert "baostock" in data["registry"]["providers"]
    assert data["registry"]["providers"]["baostock"]["status"] in ("healthy", "degraded")


def test_root_serves_frontend(client):
    r = client.get("/")
    assert r.status_code == 200
    # 返回 HTML
    assert "text/html" in r.headers.get("content-type", "")