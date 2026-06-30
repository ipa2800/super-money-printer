"""AkShareProvider — 宏观指标 + 实时行情主数据源。

支持的 indicator (来自 spec §2.3.2):
  - mainflow       (ak.stock_market_fund_flow)        主力净流入
  - bond_10y       (ak.bond_zh_us_rate)                10年国债
  - shibor_on      (ak.macro_china_shibor_all)         SHIBOR 隔夜
  - usd_cny        (ak.currency_boc_safe)              美元/人民币
  - pmi_mfg        (ak.macro_china_pmi)                制造业 PMI
  - m2             (ak.macro_china_money_supply)       M2 同比
  - cpi            (ak.macro_china_cpi)                CPI
  - lpr            (ak.macro_china_lpr)                LPR
  - etf_realtime   (ak.fund_etf_spot_em)               ETF 实时行情 33字段

SSL: spec 要求 per-request disable, akshare 内部用 requests 不暴露 verify 参数,
所以我们在 import 前 monkeypatch ssl._create_default_https_context, 进程级;
只在引用 AkShareProvider 时触发 (lazy import inside methods).
"""
from __future__ import annotations

import asyncio
import logging
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from backend.providers.akshare.field_mapping import map_fields, parse_month_label
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


# ponytail: 进程级 monkeypatch, 仅 AkShareProvider 实际 import akshare 时触发一次。
# 比 reference 全局无条件 patch 略好: 别的 Provider 不用 SSL patch
_ssl_patched = False


def _patch_ssl_no_verify() -> None:
    global _ssl_patched
    if _ssl_patched:
        return
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ssl._create_default_https_context = lambda *a, **kw: ctx
    _ssl_patched = True


def _ensure_akshare():
    """Lazy import akshare, 同时 patch SSL. 第一次慢, 后续快。"""
    _patch_ssl_no_verify()
    import akshare as ak
    return ak


# 指标 → (akshare函数名, freq-str)
# freq: D = 日频, M = 月频
INDICATOR_FNS = {
    "mainflow":   ("stock_market_fund_flow",    "D"),
    "bond_10y":   ("bond_zh_us_rate",           "D"),
    "shibor_on":  ("macro_china_shibor_all",    "D"),
    "usd_cny":    ("currency_boc_safe",         "D"),
    "pmi_mfg":    ("macro_china_pmi",           "M"),
    "m2":         ("macro_china_money_supply",  "M"),
    "cpi":        ("macro_china_cpi",           "M"),
    "lpr":        ("macro_china_lpr",           "M"),
}

# 每个 indicator 的 value 列名 (在 map_fields 之后的英文列名)
INDICATOR_VALUE_COL = {
    "mainflow":  "value",
    "bond_10y":  "value",
    "shibor_on": "value",
    "usd_cny":   "raw_value",     # 后续 ÷100
    "pmi_mfg":   "value",         # 制造业-指数 直接是指数
    "m2":        "value_yoy",     # M2 同比 %
    "cpi":       "value_yoy",     # CPI 同比 %
    "lpr":       "lpr_1y",        # LPR 用 lpr_1y 字段
}


@dataclass
class AkShareProvider(BaseProvider):
    name: str = "akshare"
    display_name: str = "AkShare"
    priority: int = 5
    supports_freq: list[KLineFreq] = field(default_factory=list)
    rate_limit_per_minute: int = 20
    supported_indicators: set[str] = field(default_factory=lambda: {
        "mainflow", "bond_10y", "shibor_on", "usd_cny",
        "pmi_mfg", "m2", "cpi", "lpr", "etf_realtime",
    })

    _last_success: Optional[datetime] = None
    _error_count: int = 0

    def login(self) -> None:
        # 触发 lazy import + SSL patch
        _ensure_akshare()
        log.info("akshare ready (ssl patched)")

    def logout(self) -> None:
        pass

    @with_retry("akshare", max_attempts=3)
    async def fetch(
        self,
        indicator: str,
        date_from: date,
        date_to: date,
        freq: Optional[KLineFreq] = None,
        symbol: Optional[str] = None,
    ) -> list[FetchResult]:
        if indicator == "etf_realtime":
            return await self._fetch_etf_realtime()
        if indicator not in INDICATOR_FNS:
            raise DataNotAvailableError(self.name, f"unsupported indicator: {indicator}")

        ak = _ensure_akshare()
        fn_name, _ = INDICATOR_FNS[indicator]
        fn = getattr(ak, fn_name)
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, fn)

        if df is None or df.empty:
            raise DataNotAvailableError(self.name, f"{fn_name} returned empty")

        df = map_fields(df, indicator)

        # 解析 date 列 (月频用 parse_month_label, 日频用 to_datetime)
        results = self._df_to_results(df, indicator, date_from, date_to)

        self._last_success = datetime.now()
        self._error_count = 0
        return results

    # ── 内部 ──
    def _df_to_results(
        self, df, indicator: str, date_from: date, date_to: date
    ) -> list[FetchResult]:
        results: list[FetchResult] = []
        value_col = INDICATOR_VALUE_COL.get(indicator, "value")
        for _, row in df.iterrows():
            d = self._parse_date(row.get("date"), indicator)
            if d is None:
                continue
            if d < date_from or d > date_to:
                continue
            v = row.get(value_col)
            if v is None or (isinstance(v, float) and v != v):  # NaN check
                continue
            try:
                value = float(v)
            except (TypeError, ValueError):
                continue
            # usd_cny 特殊处理: BOC 数据 ×100, ÷100 转真实汇率
            if indicator == "usd_cny":
                value = value / 100.0
            # mainflow 特殊处理: akshare 返回的是元, ÷1e8 转亿元
            elif indicator == "mainflow":
                value = value / 1e8
            results.append(
                FetchResult(
                    indicator=indicator,
                    date=d,
                    source=self.name,
                    value=value,
                    fetched_at=datetime.now(),
                    raw_data=row.to_dict(),
                )
            )
        return results

    @staticmethod
    def _parse_date(raw: Any, indicator: str) -> Optional[date]:
        if raw is None:
            return None
        s = str(raw).strip()
        # 月频: "2026年05月份"
        if "年" in s and "月" in s:
            iso = parse_month_label(s)
            if iso:
                try:
                    y, m = iso.split("-")
                    return date(int(y), int(m), 1)
                except (ValueError, IndexError):
                    return None
            return None
        # 日频: 多种格式尝试
        for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        # pandas Timestamp?
        try:
            return raw.date() if hasattr(raw, "date") else None
        except Exception:
            return None

    async def _fetch_etf_realtime(self) -> list[FetchResult]:
        """ETF 实时行情 — 一次性取全市场, 33 字段。"""
        ak = _ensure_akshare()
        loop = asyncio.get_running_loop()
        df = await loop.run_in_executor(None, ak.fund_etf_spot_em)
        if df is None or df.empty:
            raise DataNotAvailableError(self.name, "fund_etf_spot_em returned empty")
        df = map_fields(df, "etf_realtime")
        results: list[FetchResult] = []
        now = datetime.now()
        for _, row in df.iterrows():
            code = row.get("code")
            if not code:
                continue
            try:
                close = float(row.get("close", 0) or 0)
            except (TypeError, ValueError):
                continue
            results.append(
                FetchResult(
                    indicator="etf_realtime",
                    date=now.date(),
                    source=self.name,
                    symbol=str(code),
                    value=close,
                    fields={k: (None if pd_isnan(v) else v) for k, v in row.to_dict().items()},
                    fetched_at=now,
                    raw_data=row.to_dict(),
                )
            )
        return results

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
            message=f"supports={sorted(self.supported_indicators)}",
        )


def pd_isnan(v: Any) -> bool:
    try:
        import math
        return math.isnan(float(v))
    except (TypeError, ValueError):
        return False