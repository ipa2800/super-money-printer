"""Baostock Provider — K线主数据源 (日/周/月, 含换手率)。"""
from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

import baostock as bs

from backend.providers.base import (
    BaseProvider,
    FetchResult,
    HealthReport,
    KLineFreq,
    ProviderStatus,
)
from backend.providers.exceptions import DataNotAvailableError, ProviderError
from backend.providers.retry import with_retry

log = logging.getLogger(__name__)


# bs.login() 是进程级同步阻塞调用, lifespan 里调一次即可
_login_lock = threading.Lock()
_logged_in: bool = False


def _ensure_login() -> None:
    global _logged_in
    with _login_lock:
        if _logged_in:
            return
        # baostock 默认匿名登录 (无账号密码)
        lg = bs.login()
        if lg.error_code != "0":
            raise ProviderError("baostock", f"login failed: {lg.error_msg}")
        _logged_in = True
        log.info("baostock logged in")


def _ensure_logout() -> None:
    global _logged_in
    with _login_lock:
        if _logged_in:
            bs.logout()
            _logged_in = False


@dataclass
class BaostockProvider(BaseProvider):
    name: str = "baostock"
    display_name: str = "Baostock"
    priority: int = 1
    supports_freq: list[KLineFreq] = field(
        default_factory=lambda: [KLineFreq.DAILY, KLineFreq.WEEKLY, KLineFreq.MONTHLY]
    )
    rate_limit_per_minute: int = 60
    supported_indicators: set[str] = field(default_factory=lambda: {"kline"})

    _last_success: Optional[datetime] = None
    _error_count: int = 0

    # ── 生命周期 ──
    def login(self) -> None:
        _ensure_login()

    def logout(self) -> None:
        _ensure_logout()

    # ── fetch ──
    @with_retry("baostock", max_attempts=3)
    async def fetch(
        self,
        indicator: str,
        date_from: date,
        date_to: date,
        freq: Optional[KLineFreq] = None,
        symbol: Optional[str] = None,
    ) -> list[FetchResult]:
        if indicator != "kline":
            raise DataNotAvailableError(self.name, f"unsupported indicator: {indicator}")
        if freq is None:
            freq = KLineFreq.DAILY
        if freq not in self.supports_freq:
            raise DataNotAvailableError(self.name, f"freq not supported: {freq.value}")
        if symbol is None:
            raise ProviderError(self.name, "kline fetch requires symbol (e.g. 'sh.510050')")

        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(
            None, self._sync_query_kline, symbol, freq, date_from, date_to
        )
        self._last_success = datetime.now()
        self._error_count = 0
        return rows

    def _sync_query_kline(
        self, symbol: str, freq: KLineFreq, date_from: date, date_to: date
    ) -> list[FetchResult]:
        """同步阻塞调用 baostock query_history_k_data_plus。"""
        _ensure_login()
        rs = bs.query_history_k_data_plus(
            code=symbol,
            fields="date,code,open,high,low,close,volume,amount,turn",
            start_date=date_from.isoformat(),
            end_date=date_to.isoformat(),
            frequency=freq.value,
            adjustflag="2",  # 前复权
        )
        if rs.error_code != "0":
            raise ProviderError(self.name, f"query error: {rs.error_msg}")

        results: list[FetchResult] = []
        while (rs.error_code == "0") and rs.next():
            row = rs.get_row_data()
            # row 是 list, 列名需对照 fields
            d = dict(zip(["date", "code", "open", "high", "low", "close",
                          "volume", "amount", "turn"], row))
            try:
                results.append(
                    FetchResult(
                        indicator="kline",
                        date=date.fromisoformat(d["date"]),
                        source=self.name,
                        symbol=d["code"],
                        freq=freq,
                        fields={
                            "open":   float(d["open"]),
                            "high":   float(d["high"]),
                            "low":    float(d["low"]),
                            "close":  float(d["close"]),
                            "volume": float(d["volume"]) if d["volume"] else None,
                            "amount": float(d["amount"]) if d["amount"] else None,
                            "turn":   float(d["turn"]) if d["turn"] else None,
                        },
                        fetched_at=datetime.now(),
                        raw_data=d,
                    )
                )
            except (ValueError, KeyError) as e:
                log.warning(f"[{self.name}] skip row: {e}")
                continue
        return results

    # ── health ──
    def health_check(self) -> HealthReport:
        # ponytail: 不发起网络,仅看本地状态
        if self._error_count >= 5:
            status = ProviderStatus.UNAVAILABLE
        elif self._error_count >= 1:
            status = ProviderStatus.DEGRADED
        else:
            status = ProviderStatus.HEALTHY
        return HealthReport(
            status=status,
            latency_ms=0.0,
            last_success=self._last_success,
            error_count=self._error_count,
            message=f"logged_in={_logged_in}",
        )