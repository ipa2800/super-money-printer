"""TushareProvider — K线 备选 (依赖 TUSHARE_TOKEN, 没 token 时 provider.fetch 抛 ProviderError 让 registry fallback)。"""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from backend.providers.base import (
    BaseProvider,
    FetchResult,
    HealthReport,
    KLineFreq,
    ProviderStatus,
)
from backend.providers.exceptions import DataNotAvailableError, ProviderError

log = logging.getLogger(__name__)


# baostock 风格代码 (sh.000300) → tushare ts_code (000300.SH)
def _bs_to_ts(symbol: str) -> str:
    if "." not in symbol:
        return symbol.upper()
    market, code = symbol.split(".", 1)
    suffix = "SH" if market.lower() == "sh" else "SZ"
    return f"{code}.{suffix}"


def _freq_to_tushare(freq: KLineFreq) -> str:
    return {"d": "D", "w": "W", "m": "M"}.get(freq.value, "D")


@dataclass
class TushareProvider(BaseProvider):
    name: str = "tushare"
    display_name: str = "Tushare"
    priority: int = 2  # > baostock (1) → 作为 fallback
    supports_freq: list[KLineFreq] = field(
        default_factory=lambda: [KLineFreq.DAILY, KLineFreq.WEEKLY, KLineFreq.MONTHLY]
    )
    rate_limit_per_minute: int = 60
    supported_indicators: set[str] = field(default_factory=lambda: {"kline"})

    _last_success: Optional[datetime] = None
    _error_count: int = 0
    _pro: Any = None

    def login(self) -> None:
        token = os.environ.get("TUSHARE_TOKEN", "").strip()
        if not token:
            raise ProviderError(self.name, "TUSHARE_TOKEN env var not set; provider disabled")
        import tushare as ts
        self._pro = ts.pro_api(token)
        log.info(f"tushare ready (token len={len(token)})")

    def logout(self) -> None:
        self._pro = None

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
        if self._pro is None:
            raise ProviderError(self.name, "not logged in (no token)")
        if freq is None:
            freq = KLineFreq.DAILY
        if freq not in self.supports_freq:
            raise DataNotAvailableError(self.name, f"freq not supported: {freq.value}")
        if symbol is None:
            raise ProviderError(self.name, "kline fetch requires symbol")

        ts_code = _bs_to_ts(symbol)
        ts_freq = _freq_to_tushare(freq)
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(
            None, self._sync_query, ts_code, ts_freq, date_from, date_to
        )
        self._last_success = datetime.now()
        self._error_count = 0

        results: list[FetchResult] = []
        for _, row in df.iterrows():
            try:
                results.append(
                    FetchResult(
                        indicator="kline",
                        date=date.fromisoformat(str(row["trade_date"])),
                        source=self.name,
                        symbol=symbol,
                        freq=freq,
                        fields={
                            "open":   float(row["open"]),
                            "high":   float(row["high"]),
                            "low":    float(row["low"]),
                            "close":  float(row["close"]),
                            "volume": float(row.get("vol", 0) or 0),
                            "amount": float(row.get("amount", 0) or 0) if "amount" in row.index else None,
                        },
                        fetched_at=datetime.now(),
                        raw_data=row.to_dict(),
                    )
                )
            except (ValueError, KeyError) as e:
                log.warning(f"[{self.name}] skip row: {e}")
                continue
        return results

    def _sync_query(self, ts_code: str, freq: str, date_from: date, date_to: date):
        if freq == "D":
            df = self._pro.daily(ts_code=ts_code, start_date=date_from.strftime("%Y%m%d"),
                                 end_date=date_to.strftime("%Y%m%d"))
        elif freq == "W":
            df = self._pro.weekly(ts_code=ts_code, start_date=date_from.strftime("%Y%m%d"),
                                  end_date=date_to.strftime("%Y%m%d"))
        else:
            df = self._pro.monthly(ts_code=ts_code, start_date=date_from.strftime("%Y%m%d"),
                                   end_date=date_to.strftime("%Y%m%d"))
        if df is None or df.empty:
            raise DataNotAvailableError(self.name, f"empty result for {ts_code}")
        return df

    def health_check(self) -> HealthReport:
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
            message=f"logged_in={self._pro is not None}",
        )