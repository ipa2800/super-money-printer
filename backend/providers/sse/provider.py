"""SSEProvider — 上交所 ETF 份额主数据源 (spec §2.3.2).

URL: https://query.sse.com.cn/commonQuery.do
Params: isPagination=true, pageHelp.pageSize=10000,
        sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L,
        STAT_DATE=YYYY-MM-DD  (可选, 不传返回最新)
Headers: Referer: https://www.sse.com.cn/
Response: JSON data_json["result"]
Fields: SEC_CODE, SEC_NAME, ETF_TYPE, STAT_DATE, TOT_VOL (亿份 → ×10000)
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from io import BytesIO
from typing import Any, Optional

import httpx

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

URL = "https://query.sse.com.cn/commonQuery.do"
SQL_ID = "COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L"


@dataclass
class SSEProvider(BaseProvider):
    name: str = "sse"
    display_name: str = "上海证券交易所"
    priority: int = 1
    supports_freq: list[KLineFreq] = field(default_factory=list)
    rate_limit_per_minute: int = 30
    supported_indicators: set[str] = field(default_factory=lambda: {"etf_shares"})

    _last_success: Optional[datetime] = None
    _error_count: int = 0

    def login(self) -> None:
        pass

    def logout(self) -> None:
        pass

    @with_retry("sse", max_attempts=3)
    async def fetch(
        self,
        indicator: str,
        date_from: date,
        date_to: date,
        freq: Optional[KLineFreq] = None,
        symbol: Optional[str] = None,
    ) -> list[FetchResult]:
        if indicator != "etf_shares":
            raise DataNotAvailableError(self.name, f"unsupported indicator: {indicator}")

        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(None, self._sync_query, date_from, date_to)
        if not rows:
            raise DataNotAvailableError(self.name, "SSE returned no rows")

        self._last_success = datetime.now()
        self._error_count = 0
        return rows

    def _sync_query(self, date_from: date, date_to: date) -> list[FetchResult]:
        """同步阻塞拉 SSE 历史份额 (逐日 STAT_DATE 拉一次合并)。

        SSE 不支持范围查询, 只能按单日查; date_from..date_to 内逐日循环。
        """
        results: list[FetchResult] = []
        # 限制最多 30 天 (历史约 20+ 日), 超出截断
        days = (date_to - date_from).days + 1
        if days > 30:
            log.info(f"[sse] range {days}d too long, truncate to 30d")
            days = 30
            date_from = date_to - timedelta(days=29)

        with httpx.Client(timeout=15.0, verify=False) as client:
            for offset in range(days):
                d = date_to - timedelta(days=offset)
                try:
                    params = {
                        "isPagination": "true",
                        "pageHelp.pageSize": "10000",
                        "sqlId": SQL_ID,
                        "STAT_DATE": d.isoformat(),
                    }
                    headers = {"Referer": "https://www.sse.com.cn/"}
                    r = client.get(URL, params=params, headers=headers)
                    if r.status_code != 200:
                        log.warning(f"[sse] {d} HTTP {r.status_code}")
                        continue
                    data = r.json()
                    rows = data.get("result", [])
                    if not isinstance(rows, list):
                        continue
                    for row in rows:
                        try:
                            code = row.get("SEC_CODE")
                            if not code:
                                continue
                            tot_vol = row.get("TOT_VOL")  # 亿份
                            if tot_vol is None:
                                continue
                            shares = float(tot_vol) * 10000.0  # 亿份 → 份
                            results.append(
                                FetchResult(
                                    indicator="etf_shares",
                                    date=d,
                                    source=self.name,
                                    symbol=str(code),
                                    value=shares,
                                    fields={
                                        "name": row.get("SEC_NAME"),
                                        "etf_type": row.get("ETF_TYPE"),
                                        "shares_raw": tot_vol,
                                    },
                                    fetched_at=datetime.now(),
                                    raw_data=row,
                                )
                            )
                        except (ValueError, TypeError) as e:
                            log.warning(f"[sse] skip row: {e}")
                except httpx.HTTPError as e:
                    log.warning(f"[sse] {d} network error: {e}")
                    continue
        return results

    def health_check(self) -> HealthReport:
        status = (
            ProviderStatus.UNAVAILABLE if self._error_count >= 5
            else ProviderStatus.DEGRADED if self._error_count >= 1
            else ProviderStatus.HEALTHY
        )
        return HealthReport(
            status=status,
            latency_ms=0.0,
            last_success=self._last_success,
            error_count=self._error_count,
            message=f"endpoint={URL}",
        )