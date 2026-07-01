"""SectorProvider — 板块/概念 行情 (akshare 适配).

snapshot: 一次性拉全部 行业+概念 (≈80+300=380 个) 的实时快照, 字段 12 个中文列.
history:  单个板块/概念的 K 线历史, symbol 格式 '<type>:<code>' (e.g. 'industry:BK0473').

中文→英文 映射在 _SPOT_COLS / _HIST_COLS, 跟 service 层字段名一致.
"""
from __future__ import annotations

import asyncio
import logging
import ssl
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any, Optional

from backend.providers.akshare.provider import _ensure_akshare
from backend.providers.base import (
    BaseProvider,
    FetchResult,
    HealthReport,
    KLineFreq,
    ProviderStatus,
)
from backend.providers.exceptions import DataNotAvailableError
from backend.providers.retry import with_retry

log = logging.getLogger(__name__)


# akshare 实时快照: 中文列名 → 英文 (跟 sector_cache schema 对齐)
_SPOT_COLS = {
    "板块名称": "name",
    "板块代码": "code",
    "最新价":   "price",
    "涨跌额":   "change",
    "涨跌幅":   "pct_chg",
    "总市值":   "total_mv",
    "换手率":   "turnover",
    "上涨家数": "up_count",
    "下跌家数": "down_count",
    "领涨股票": "leader",
    "领涨股票-涨跌幅": "leader_pct",
}

# akshare 历史: 中文列名 → 英文 (跟 sector_history schema 对齐)
_HIST_COLS = {
    "日期":   "date",
    "开盘":   "open",
    "收盘":   "close",
    "最高":   "high",
    "最低":   "low",
    "成交量": "volume",
    "成交额": "amount",
    "涨跌幅": "pct_chg",
    "涨跌额": "change",
}


@dataclass
class SectorProvider(BaseProvider):
    name: str = "sector"
    display_name: str = "板块/概念 (akshare)"
    priority: int = 5
    supports_freq: list[KLineFreq] = field(default_factory=list)
    rate_limit_per_minute: int = 30
    supported_indicators: set[str] = field(default_factory=lambda: {
        "sector_snapshot", "sector_history",
        "sector_fund_flow", "sector_constituents", "limit_up_pool",
    })

    _last_success: Optional[datetime] = None
    _error_count: int = 0

    def login(self) -> None:
        _ensure_akshare()
        log.info("sector provider ready")

    def logout(self) -> None:
        pass

    @with_retry("sector", max_attempts=3)
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
        if indicator == "sector_history":
            return await self._fetch_history(symbol, date_from, date_to)
        if indicator == "sector_fund_flow":
            return await self._fetch_fund_flow()
        if indicator == "sector_constituents":
            return await self._fetch_constituents(symbol)
        if indicator == "limit_up_pool":
            return await self._fetch_limit_up_pool(date_from)
        raise DataNotAvailableError(self.name, f"unsupported indicator: {indicator}")

    # ── snapshot: 全部 行业+概念 ──
    async def _fetch_snapshot(self) -> list[FetchResult]:
        ak = _ensure_akshare()
        loop = asyncio.get_running_loop()
        results: list[FetchResult] = []
        # 行业 + 概念 各拉一次, 合并. 并发避免串行等待.
        tasks = [
            loop.run_in_executor(None, ak.stock_board_industry_spot_em),
            loop.run_in_executor(None, ak.stock_board_concept_spot_em),
        ]
        try:
            dfs = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            raise DataNotAvailableError(self.name, f"snapshot gather failed: {e}")

        now = datetime.now()
        type_map = [("industry", dfs[0]), ("concept", dfs[1])]
        for sector_type, df in type_map:
            if isinstance(df, Exception) or df is None or df.empty:
                log.warning(f"[{sector_type}] snapshot fetch failed: {df if isinstance(df, Exception) else 'empty'}")
                continue
            for _, row in df.iterrows():
                code = _safe_str(row.get("板块代码"))
                if not code:
                    continue
                results.append(
                    FetchResult(
                        indicator="sector_snapshot",
                        date=now.date(),
                        source=self.name,
                        symbol=f"{sector_type}:{code}",   # 给 history 调用用
                        value=_safe_float(row.get("最新价")),
                        fields={eng: _safe_val(row.get(cn)) for cn, eng in _SPOT_COLS.items() if cn != "板块代码"} | {"type": sector_type},
                        fetched_at=now,
                        raw_data=row.to_dict(),
                    )
                )

        if not results:
            raise DataNotAvailableError(self.name, "snapshot empty (both industry+concept failed)")
        self._last_success = datetime.now()
        self._error_count = 0
        return results

    # ── history: 单个板块/概念 的 K 线 ──
    async def _fetch_history(
        self,
        symbol: Optional[str],
        date_from: date,
        date_to: date,
    ) -> list[FetchResult]:
        # symbol 格式: '<type>:<code>'  e.g. 'industry:BK0473' | 'concept:BKXXXX'
        if not symbol or ":" not in symbol:
            raise DataNotAvailableError(self.name, f"sector_history needs symbol='<type>:<code>', got {symbol!r}")
        sector_type, em_code = symbol.split(":", 1)

        ak = _ensure_akshare()
        loop = asyncio.get_running_loop()
        if sector_type == "industry":
            fn = ak.stock_board_industry_hist_em
        elif sector_type == "concept":
            fn = ak.stock_board_concept_hist_em
        else:
            raise DataNotAvailableError(self.name, f"unknown sector type: {sector_type}")

        # akshare period: 日k / 周k / 月k. 默认日.
        period = "日k"
        # akshare date 格式 YYYYMMDD
        beg = date_from.strftime("%Y%m%d")
        end = date_to.strftime("%Y%m%d")
        try:
            df = await loop.run_in_executor(None, lambda: fn(symbol=em_code, start_date=beg, end_date=end, period=period, adjust=""))
        except Exception as e:
            raise DataNotAvailableError(self.name, f"hist fetch failed for {symbol}: {e}")

        if df is None or df.empty:
            raise DataNotAvailableError(self.name, f"hist empty for {symbol} {beg}..{end}")

        results: list[FetchResult] = []
        for _, row in df.iterrows():
            d = _parse_date_str(row.get("日期"))
            if d is None or d < date_from or d > date_to:
                continue
            try:
                fields = {
                    eng: _safe_val(row.get(cn))
                    for cn, eng in _HIST_COLS.items() if cn != "日期"
                }
                results.append(
                    FetchResult(
                        indicator="sector_history",
                        date=d,
                        source=self.name,
                        symbol=symbol,
                        value=_safe_float(row.get("收盘")),
                        fields=fields,
                        fetched_at=datetime.now(),
                        raw_data=row.to_dict(),
                    )
                )
            except (ValueError, KeyError, TypeError) as e:
                log.debug(f"[{symbol}] skip row: {e}")
                continue

        if not results:
            raise DataNotAvailableError(self.name, f"no hist rows for {symbol} in {date_from}..{date_to}")
        return results

    # ── fund_flow: 板块资金流 (同花顺, "即时" 实时快照) ──
    async def _fetch_fund_flow(self) -> list[FetchResult]:
        """ak.stock_fund_flow_industry/concept(symbol='即时') — 同花顺口径.
        返回列: 序号, 行业, 行业指数, 行业-涨跌幅, 流入资金, 流出资金, 净额, 公司家数,
                领涨股, 领涨股-涨跌幅, 当前价. (无 BK 代码, 名字匹配由 service 层做)
        """
        ak = _ensure_akshare()
        loop = asyncio.get_running_loop()
        now = datetime.now()
        results: list[FetchResult] = []
        tasks = [
            loop.run_in_executor(None, lambda: ak.stock_fund_flow_industry(symbol="即时")),
            loop.run_in_executor(None, lambda: ak.stock_fund_flow_concept(symbol="即时")),
        ]
        try:
            dfs = await asyncio.gather(*tasks, return_exceptions=True)
        except Exception as e:
            raise DataNotAvailableError(self.name, f"fund_flow gather failed: {e}")

        for sector_type, df in [("industry", dfs[0]), ("concept", dfs[1])]:
            if isinstance(df, Exception) or df is None or df.empty:
                log.warning(f"[{sector_type}] fund_flow fetch failed: {df if isinstance(df, Exception) else 'empty'}")
                continue
            for _, row in df.iterrows():
                name = _safe_str(row.get("行业"))
                if not name:
                    continue
                # symbol 暂存 name, service 层用 sector_cache name→code 映射替换
                results.append(FetchResult(
                    indicator="sector_fund_flow",
                    date=now.date(),
                    source=self.name,
                    symbol=f"{sector_type}:{name}",   # placeholder, 写表时替换为 BK code
                    fields={
                        "name":   name,
                        "type":   sector_type,
                        "price":  _safe_float(row.get("最新价")),
                        "pct_chg": _safe_float(row.get("行业-涨跌幅")),
                        "inflow": _safe_float(row.get("流入资金")),
                        "outflow": _safe_float(row.get("流出资金")),
                        "net":    _safe_float(row.get("净额")),
                    },
                    fetched_at=now,
                    raw_data=row.to_dict(),
                ))
        if not results:
            raise DataNotAvailableError(self.name, "fund_flow empty")
        self._last_success = datetime.now()
        self._error_count = 0
        return results

    # ── constituents: 板块成分股 (用于计算涨停密度) ──
    async def _fetch_constituents(self, symbol: Optional[str]) -> list[FetchResult]:
        """symbol='<type>:<code>'. 拉该板块下所有成分股.
        返回列含 代码 + 名称 (够 service 写 sector_constituents).
        """
        if not symbol or ":" not in symbol:
            raise DataNotAvailableError(self.name, f"sector_constituents needs symbol='<type>:<code>', got {symbol!r}")
        sector_type, em_code = symbol.split(":", 1)
        ak = _ensure_akshare()
        loop = asyncio.get_running_loop()
        if sector_type == "industry":
            fn = ak.stock_board_industry_cons_em
        elif sector_type == "concept":
            fn = ak.stock_board_concept_cons_em
        else:
            raise DataNotAvailableError(self.name, f"unknown sector type: {sector_type}")
        try:
            df = await loop.run_in_executor(None, lambda: fn(symbol=em_code))
        except Exception as e:
            raise DataNotAvailableError(self.name, f"constituents fetch failed for {symbol}: {e}")
        if df is None or df.empty:
            raise DataNotAvailableError(self.name, f"constituents empty for {symbol}")
        results: list[FetchResult] = []
        for _, row in df.iterrows():
            sc = _safe_str(row.get("代码"))
            if not sc:
                continue
            results.append(FetchResult(
                indicator="sector_constituents",
                date=datetime.now().date(),
                source=self.name,
                symbol=symbol,
                fields={
                    "stock_code": sc,
                    "stock_name": _safe_str(row.get("名称")),
                },
                fetched_at=datetime.now(),
                raw_data=row.to_dict(),
            ))
        if not results:
            raise DataNotAvailableError(self.name, f"no constituents for {symbol}")
        return results

    # ── limit_up_pool: 涨停股池 (日级, akshare 限制近 30 个交易日) ──
    async def _fetch_limit_up_pool(self, target_date: date) -> list[FetchResult]:
        """ak.stock_zt_pool_em(date='YYYYMMDD'). 拉某日涨停股, 含 连板数 + 所属行业.
        返回列: 序号, 代码, 名称, 涨跌幅, 最新价, 成交额, 流通市值, 总市值, 换手率,
                封板资金, 首次封板时间, 最后封板时间, 炸板次数, 涨停统计, 连板数, 所属行业.
        """
        ak = _ensure_akshare()
        loop = asyncio.get_running_loop()
        date_str = target_date.strftime("%Y%m%d")
        try:
            df = await loop.run_in_executor(None, lambda: ak.stock_zt_pool_em(date=date_str))
        except Exception as e:
            # akshare 限制 30 日内; 超出 / 周末/节假日 会 raise 或返回空
            log.warning(f"[limit_up_pool] fetch failed for {date_str}: {e}")
            raise DataNotAvailableError(self.name, f"limit_up_pool failed for {date_str}: {e}")
        if df is None or df.empty:
            # 周末/节假日返回空, 不算错
            return []
        results: list[FetchResult] = []
        for _, row in df.iterrows():
            code = _safe_str(row.get("代码"))
            name = _safe_str(row.get("名称"))
            if not code or not name:
                continue
            results.append(FetchResult(
                indicator="limit_up_pool",
                date=target_date,
                source=self.name,
                symbol=code,
                fields={
                    "name": name,
                    "pct_chg": _safe_float(row.get("涨跌幅")),
                    "limit_up_time": _safe_str(row.get("首次封板时间")),
                    "continuous": _safe_int(row.get("连板数")),
                    "industry": _safe_str(row.get("所属行业")),
                },
                fetched_at=datetime.now(),
                raw_data=row.to_dict(),
            ))
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


# ── helpers ──
def _safe_str(v: Any) -> Optional[str]:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        f = float(v)
        return None if f != f else f  # NaN → None
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def _safe_val(v: Any) -> Any:
    """Snapshot 字段值: float/int/str 都原样, NaN/None → None."""
    if v is None:
        return None
    if isinstance(v, (int, float, str, bool)):
        if isinstance(v, float) and v != v:
            return None
        return v
    s = str(v).strip()
    return s if s else None


def _parse_date_str(s: Any) -> Optional[date]:
    if s is None:
        return None
    t = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(t, fmt).date()
        except ValueError:
            continue
    return None