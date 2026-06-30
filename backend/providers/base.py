"""BaseProvider 抽象基类 — spec §4.1。"""
from __future__ import annotations

import abc
from dataclasses import dataclass, field
from datetime import date, datetime
from enum import Enum
from typing import Any, Optional


class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"


class KLineFreq(Enum):
    """K线频率枚举 (实测验证: baostock 支持 d/w/m)"""
    DAILY = "d"
    WEEKLY = "w"
    MONTHLY = "m"


@dataclass
class FetchResult:
    """标准化数据获取结果。"""
    indicator: str           # 指标名称, 如 "kline", "etf_shares"
    date: date               # 数据日期
    source: str              # 数据源名称, 如 "baostock", "akshare"
    fetched_at: datetime = field(default_factory=datetime.now)
    raw_data: Optional[dict] = None
    confidence: float = 1.0
    # K线专用字段
    symbol: Optional[str] = None         # "sh.510050"
    freq: Optional[KLineFreq] = None     # d/w/m
    fields: Optional[dict[str, Any]] = None  # {open, high, low, close, volume, ...}
    # 标量指标
    value: Any = None


@dataclass
class HealthReport:
    status: ProviderStatus
    latency_ms: float
    last_success: Optional[datetime]
    error_count: int
    message: str = ""


class BaseProvider(abc.ABC):
    """数据源抽象基类。"""

    name: str                                # 唯一标识, 如 "baostock"
    display_name: str                        # 显示名
    priority: int                            # 数字越小优先级越高
    supports_freq: list[KLineFreq] = field(default_factory=list)
    rate_limit_per_minute: int = 30
    supported_indicators: set[str] = field(default_factory=set)

    # ── 生命周期 ──
    def login(self) -> None:
        """可选: 进程级登录 (如 baostock)。默认无操作。"""

    def logout(self) -> None:
        """可选: 进程级登出。默认无操作。"""

    # ── 数据获取 ──
    @abc.abstractmethod
    async def fetch(
        self,
        indicator: str,
        date_from: date,
        date_to: date,
        freq: Optional[KLineFreq] = None,
        symbol: Optional[str] = None,
    ) -> list[FetchResult]:
        """获取指定日期范围的数据。"""

    @abc.abstractmethod
    def health_check(self) -> HealthReport:
        """健康检查 (同步, 不发起网络请求或仅 ping 心跳)。"""

    # ── 工具方法 ──
    def supports(self, indicator: str) -> bool:
        return indicator in self.supported_indicators

    def supports_kline_freq(self, freq: KLineFreq) -> bool:
        return freq in self.supports_freq