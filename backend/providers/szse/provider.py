"""SZSEProvider — 深交所 ETF 份额 (仅今日快照, 无历史).

URL: https://fund.szse.cn/api/report/ShowReport
Params: SHOWTYPE=xlsx, CATALOGID=1000_lf, TABKEY=tab1
返回 XLSX, 含字段: 基金代码, 基金简称, 当前规模(份), 净值, 上市日期 等.
akshare 1.18.64 fund_etf_scale_szse() 有 bug (pd.read_excel 不接受 bytes),
这里手动 pd.read_excel(BytesIO(resp.content), engine='openpyxl').
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from io import BytesIO
from typing import Any, Optional

import httpx
import pandas as pd

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

URL = "https://fund.szse.cn/api/report/ShowReport"


@dataclass
class SZSEProvider(BaseProvider):
    name: str = "szse"
    display_name: str = "深圳证券交易所"
    priority: int = 1
    supports_freq: list[KLineFreq] = field(default_factory=list)
    rate_limit_per_minute: int = 10
    supported_indicators: set[str] = field(default_factory=lambda: {"etf_shares"})

    _last_success: Optional[datetime] = None
    _error_count: int = 0

    def login(self) -> None:
        pass

    def logout(self) -> None:
        pass

    @with_retry("szse", max_attempts=3)
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

        # SZSE 只返回今日快照 — date_from/date_to 参数被忽略
        loop = asyncio.get_running_loop()
        rows = await loop.run_in_executor(None, self._sync_query)
        if not rows:
            raise DataNotAvailableError(self.name, "SZSE returned no rows")

        self._last_success = datetime.now()
        self._error_count = 0
        return rows

    def _sync_query(self) -> list[FetchResult]:
        results: list[FetchResult] = []
        today = date.today()
        with httpx.Client(timeout=20.0, verify=False) as client:
            params = {"SHOWTYPE": "xlsx", "CATALOGID": "1000_lf", "TABKEY": "tab1"}
            headers = {
                "Referer": "https://fund.szse.cn/",
                "User-Agent": "Mozilla/5.0",
            }
            r = client.get(URL, params=params, headers=headers)
            if r.status_code != 200:
                raise ProviderError(self.name, f"HTTP {r.status_code}")
            try:
                # ponytail: SZSE 用 xlsx, BytesIO 包一下
                df = pd.read_excel(BytesIO(r.content), engine="openpyxl")
            except Exception as e:
                raise ProviderError(self.name, f"xlsx parse failed: {e}") from e
            if df is None or df.empty:
                return results
            # 字段: 基金代码 / 基金简称 / 当前规模(份) / 净值 / 上市日期
            for _, row in df.iterrows():
                try:
                    code = str(row.get("基金代码", "")).strip()
                    if not code or code == "nan":
                        continue
                    shares_raw = row.get("当前规模(份)")
                    if shares_raw is None:
                        continue
                    # 字段可能是 "17,921,775" 字符串, 需去逗号
                    if isinstance(shares_raw, str):
                        shares = float(shares_raw.replace(",", ""))
                    else:
                        shares = float(shares_raw)
                    results.append(
                        FetchResult(
                            indicator="etf_shares",
                            date=today,
                            source=self.name,
                            symbol=code,
                            value=shares,
                            fields={
                                "name": row.get("基金简称"),
                                "nav": row.get("净值"),
                                "ipo_date": str(row.get("上市日期", "")),
                            },
                            fetched_at=datetime.now(),
                            raw_data=row.to_dict(),
                        )
                    )
                except (ValueError, TypeError) as e:
                    log.warning(f"[szse] skip row: {e}")
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