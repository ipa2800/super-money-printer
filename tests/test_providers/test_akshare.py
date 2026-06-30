"""AkShareProvider 烟雾测试 — 验证 lazy import + SSL patch + supported_indicators。"""
from __future__ import annotations

import pytest

from backend.providers.akshare.provider import AkShareProvider, _patch_ssl_no_verify


@pytest.fixture
def provider() -> AkShareProvider:
    return AkShareProvider()


def test_supported_indicators(provider):
    assert "etf_realtime" in provider.supported_indicators
    assert "mainflow" in provider.supported_indicators
    assert "lpr" in provider.supported_indicators
    assert len(provider.supported_indicators) == 9


def test_health_check_starts_healthy(provider):
    h = provider.health_check()
    assert h.status.value == "healthy"
    assert h.error_count == 0


def test_ssl_patch_is_idempotent():
    """重复调用 _patch_ssl_no_verify 不报错, 只生效一次。"""
    _patch_ssl_no_verify()
    _patch_ssl_no_verify()
    import ssl as _ssl
    ctx = _ssl._create_default_https_context()
    assert ctx.verify_mode == _ssl.CERT_NONE
    assert ctx.check_hostname is False


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("akshare"),
    reason="akshare not installed",
)
def test_ensure_akshare_returns_module():
    """_ensure_akshare 第一次慢, 第二次快, 都返回模块。"""
    from backend.providers.akshare.provider import _ensure_akshare
    ak1 = _ensure_akshare()
    ak2 = _ensure_akshare()
    assert ak1 is ak2
    assert hasattr(ak1, "fund_etf_spot_em")