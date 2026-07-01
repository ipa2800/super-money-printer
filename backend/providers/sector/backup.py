"""SectorBackupProvider — 板块/概念 备份源 (新浪行业).

主源 (sector/akshare em) 挂了时兜底, 只覆盖行业 (≈49 个细粒度: 玻璃/船舶/水泥等).
概念维度没备份 — akshare 生态里没可用的接口.

akshare 接口: ak.stock_sector_spot(indicator="新浪行业")
字段: label / 板块 / 公司家数 / 平均价格 / 涨跌额 / 涨跌幅 / 总成交量 / 总成交额
      股票代码 / 个股-涨跌幅 / 个股-当前价 / 个股-涨跌额 / 股票名称

code 用 label (new_blhy/new_cbzz), 跟主源 BKxxxx 编码体系不冲突
(PK 是 (code, type)), 物理隔离写入 sector_cache.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any, Optional

from backend.providers.akshare.provider import _ensure_akshare
from backend.providers.base import BaseProvider, FetchResult, KLineFreq, ProviderStatus, HealthReport
from backend.providers.exceptions import DataNotAvailableError
from backend.providers.retry import with_retry

log = logging.getLogger(__name__)


def _safe_str(v: Any) -> Optional[str]:
    if v is None: return None
    s = str(v).strip()
    return s if s else None


def _safe_float(v: Any) -> Optional[float]:
    if v is None or v == "" or (isinstance(v, str) and v.strip() in ("-", "--", "")): return None
    try: return float(v)
    except (ValueError, TypeError): return None


@dataclass
class SectorBackupProvider(BaseProvider):
    name: str = "sector_backup"
    display_name: str = "板块备份 (新浪行业)"
    priority: int = 8                                       # > 主源 (5) — 失败兜底
    supports_freq: list[KLineFreq] = field(default_factory=list)
    rate_limit_per_minute: int = 10
    supported_indicators: set[str] = field(default_factory=lambda: {"sector_snapshot"})

    _last_success: Optional[datetime] = None
    _error_count: int = 0

    def login(self) -> None:
        _ensure_akshare()
        log.info("sector_backup provider ready (priority=8, only snapshot)")

    def logout(self) -> None:
        pass

    @with_retry("sector_backup", max_attempts=2)
    async def fetch(
        self,
        indicator: str,
        date_from: date,
        date_to: date,
        freq: Optional[KLineFreq] = None,
        symbol: Optional[str] = None,
    ) -> list[FetchResult]:
        if indicator == "sector_snapshot":
            return await self._fetch_snapshot()
        raise DataNotAvailableError(self.name, f"unsupported indicator: {indicator}")

    async def _fetch_snapshot(self) -> list[FetchResult]:
        ak = _ensure_akshare()
        loop = asyncio.get_running_loop()
        try:
            df = await loop.run_in_executor(
                None, lambda: ak.stock_sector_spot(indicator="新浪行业")
            )
        except Exception as e:
            raise DataNotAvailableError(self.name, f"ak.stock_sector_spot(新浪行业) failed: {e}")
        if df is None or df.empty:
            raise DataNotAvailableError(self.name, "新浪行业 snapshot empty")

        now = datetime.now()
        results: list[FetchResult] = []
        for _, row in df.iterrows():
            label = _safe_str(row.get("label"))
            name = _safe_str(row.get("板块"))
            if not label or not name:
                continue
            results.append(
                FetchResult(
                    indicator="sector_snapshot",
                    date=now.date(),
                    source=self.name,
                    symbol=f"industry:{label}",            # code = label (new_xxxx), 跟主源 BKxxxx 不撞 PK
                    value=_safe_float(row.get("平均价格")),
                    fields={
                        "name":       name,
                        "price":      _safe_float(row.get("平均价格")),
                        "change":     _safe_float(row.get("涨跌额")),
                        "pct_chg":    _safe_float(row.get("涨跌幅")),
                        "total_mv":   None,
                        "turnover":   None,
                        "up_count":   None,
                        "down_count": None,
                        "leader":     _safe_str(row.get("股票名称")),
                        "leader_pct": _safe_float(row.get("个股-涨跌幅")),
                        "type":       "industry",
                    },
                    fetched_at=now,
                    raw_data=row.to_dict(),
                )
            )

        if not results:
            raise DataNotAvailableError(self.name, "no valid rows from 新浪行业")
        self._last_success = now
        self._error_count = 0
        log.info(f"[sector_backup] 新浪行业 fetched {len(results)} rows")
        return results

    def health_check(self) -> HealthReport:
        from backend.providers.base import ProviderStatus
        if self._error_count >= 3:
            return HealthReport(status=ProviderStatus.UNAVAILABLE, error_count=self._error_count, latency_ms=0.0, message="repeated failures")
        if self._last_success and (datetime.now() - self._last_success).total_seconds() < 3600:
            return HealthReport(status=ProviderStatus.HEALTHY, last_success=self._last_success, error_count=self._error_count, latency_ms=0.0, message="ok")
        return HealthReport(status=ProviderStatus.DEGRADED, last_success=self._last_success, error_count=self._error_count, latency_ms=0.0, message="stale")