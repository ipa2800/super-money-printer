"""ProviderRegistry — 数据源注册中心。spec §4.2。"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from backend.providers.base import (
    BaseProvider,
    FetchResult,
    HealthReport,
    KLineFreq,
    ProviderStatus,
)
from backend.providers.exceptions import ProviderError

log = logging.getLogger(__name__)


class ProviderRegistry:
    """数据源注册中心: register / get_primary / fetch_with_fallback / get_status。"""

    def __init__(self) -> None:
        self._providers: dict[str, list[BaseProvider]] = {}  # indicator -> [providers]
        self._by_name: dict[str, BaseProvider] = {}

    # ── 生命周期 ──
    def register(self, provider: BaseProvider) -> None:
        """注册 Provider 到其支持的指标。"""
        self._by_name[provider.name] = provider
        for indicator in provider.supported_indicators:
            bucket = self._providers.setdefault(indicator, [])
            if provider not in bucket:
                bucket.append(provider)
            bucket.sort(key=lambda p: p.priority)
        log.info(
            f"registered {provider.name} (priority={provider.priority}) "
            f"for indicators={provider.supported_indicators}"
        )

    async def bootstrap(self) -> None:
        """启动时调: 各 provider.login()。失败抛错让 lifespan 中止。"""
        for name, p in self._by_name.items():
            try:
                p.login()
            except Exception as e:
                log.error(f"[{name}] login failed: {e}")
                raise

    async def shutdown(self) -> None:
        """关停时调: 各 provider.logout()。"""
        for name, p in self._by_name.items():
            try:
                p.logout()
            except Exception as e:
                log.warning(f"[{name}] logout failed: {e}")

    # ── 查询 ──
    def get_primary(self, indicator: str) -> Optional[BaseProvider]:
        providers = self._providers.get(indicator, [])
        for p in providers:
            if p.health_check().status != ProviderStatus.UNAVAILABLE:
                return p
        return None

    def get_all(self, indicator: str) -> list[BaseProvider]:
        providers = self._providers.get(indicator, [])
        return [p for p in providers
                if p.health_check().status != ProviderStatus.UNAVAILABLE]

    async def fetch_with_fallback(
        self,
        indicator: str,
        date_from,
        date_to,
        freq: Optional[KLineFreq] = None,
        symbol: Optional[str] = None,
    ) -> list[FetchResult]:
        """按 priority 顺序试各 provider, 合并结果 (同 (indicator,date) 保留先到的)。"""
        results: dict[tuple, FetchResult] = {}
        errors: list[str] = []
        for p in self.get_all(indicator):
            try:
                fetched = await p.fetch(indicator, date_from, date_to, freq=freq, symbol=symbol)
                for r in fetched:
                    key = (r.indicator, r.date, r.symbol or "")
                    if key not in results:
                        results[key] = r
            except ProviderError as e:
                errors.append(f"{p.name}: {e}")
                continue
        if not results and errors:
            raise ProviderError("registry", f"all providers failed: {'; '.join(errors)}")
        return list(results.values())

    def get_status(self) -> dict[str, Any]:
        """所有 provider 状态概览 — 给 /api/health 用。"""
        status: dict[str, Any] = {
            "providers": {},
            "summary": {"total": len(self._by_name), "healthy": 0, "degraded": 0, "unavailable": 0},
        }
        for name, p in self._by_name.items():
            h: HealthReport = p.health_check()
            status["providers"][name] = {
                "status": h.status.value,
                "last_success": h.last_success.isoformat() if h.last_success else None,
                "error_count": h.error_count,
                "message": h.message,
                "supports": sorted(p.supported_indicators),
            }
            status["summary"][h.status.value] += 1
        return status


# 全局单例
_registry: Optional[ProviderRegistry] = None


def get_registry() -> ProviderRegistry:
    global _registry
    if _registry is None:
        _registry = ProviderRegistry()
    return _registry


def reset_registry() -> None:
    """测试用。"""
    global _registry
    _registry = None