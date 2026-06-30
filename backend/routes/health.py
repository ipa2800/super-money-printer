"""GET /api/health — 健康检查 + Provider 状态。"""
from __future__ import annotations

from fastapi import APIRouter

from backend.providers.registry import get_registry

router = APIRouter(prefix="/api", tags=["health"])


@router.get("/health")
async def health() -> dict:
    registry = get_registry()
    return {
        "ok": True,
        "registry": registry.get_status(),
    }