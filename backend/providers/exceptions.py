"""Provider 异常。"""
from __future__ import annotations


class ProviderError(Exception):
    """数据源异常基类。"""

    def __init__(self, provider: str, message: str, original: Exception | None = None) -> None:
        self.provider = provider
        self.original = original
        super().__init__(f"[{provider}] {message}")


class RateLimitError(ProviderError):
    """速率限制。"""


class DataNotAvailableError(ProviderError):
    """数据不可用 (如非交易日 / 标的不存在)。"""