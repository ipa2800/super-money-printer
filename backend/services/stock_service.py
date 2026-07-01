"""StockService — 自选股池 CRUD + 个股数据 (kline/fund_flow/summary/news)。"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime, timedelta
from typing import Any

from backend.db.connection import get_connection
from backend.providers.base import KLineFreq
from backend.providers.registry import get_registry

log = logging.getLogger(__name__)


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


class StockService:
    def __init__(self) -> None:
        self.registry = get_registry()

    # ── pool CRUD ────────────────────────────────────────────
    @staticmethod
    def list_pool() -> list[dict[str, Any]]:
        conn = get_connection()
        rows = conn.execute(
            "SELECT code, name FROM stock_pool ORDER BY added_at"
        ).fetchall()
        return [_row_to_dict(r) for r in rows]

    @staticmethod
    def add_to_pool(code: str, name: str | None) -> None:
        from datetime import datetime, timezone
        conn = get_connection()
        conn.execute(
            "INSERT OR IGNORE INTO stock_pool (code, name, added_at) VALUES (?, ?, ?)",
            (code, name or "", datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        conn.commit()

    @staticmethod
    def remove_from_pool(code: str) -> int:
        conn = get_connection()
        cur = conn.execute("DELETE FROM stock_pool WHERE code = ?", (code,))
        conn.commit()
        return cur.rowcount

    @staticmethod
    def search(q: str) -> list[dict[str, Any]]:
        """akshare stock_info_a_code_name — 全市场代码表, 前缀/包含匹配。"""
        import akshare as ak
        df = ak.stock_info_a_code_name()
        q = (q or "").strip()
        if q:
            mask = df["code"].astype(str).str.startswith(q) | df["name"].astype(str).str.contains(q, na=False)
            df = df[mask]
        return [
            {"code": str(r["code"]), "name": str(r["name"])}
            for _, r in df.head(50).iterrows()
        ]

    # ── 单股数据 ─────────────────────────────────────────────
    async def get_kline(self, code: str, freq: str = "d", limit: int = 60) -> list[dict[str, Any]]:
        """BaostockProvider 拉日/周/月 K线。code 接受 'sh.600000' 或 '600000'。cache-first。"""
        freq_map = {"d": KLineFreq.DAILY, "w": KLineFreq.WEEKLY, "m": KLineFreq.MONTHLY}
        f = freq_map.get(freq)
        if f is None:
            raise ValueError(f"freq must be d/w/m, got {freq!r}")
        symbol = _a_share_symbol(code)

        # ponytail: cache-first, 命中阈值 ≥ 5 行才认为有效
        conn = get_connection()
        cached = conn.execute(
            """SELECT date, open, high, low, close, volume, amount, turnover, source
               FROM kline_cache WHERE symbol = ? AND freq = ?
               ORDER BY date DESC LIMIT ?""",
            (symbol, freq, limit),
        ).fetchall()
        if len(cached) >= min(limit, 5):
            return [_row_to_dict(r) for r in reversed(cached)]

        # 未命中 → 拉网络
        date_to = date.today()
        date_from = date_to - timedelta(days=limit * 3)
        results = await self.registry.fetch_with_fallback(
            "kline", date_from, date_to, freq=f, symbol=symbol,
        )
        if not results:
            return []
        conn = get_connection()
        cur = conn.cursor()
        now_iso = results[0].fetched_at.isoformat(timespec="seconds")
        for r in results:
            fld = r.fields or {}
            cur.execute(
                """INSERT OR REPLACE INTO kline_cache
                   (symbol, freq, date, open, high, low, close,
                    volume, amount, turnover, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (symbol, freq, r.date.isoformat(),
                 fld.get("open"), fld.get("high"), fld.get("low"), fld.get("close"),
                 fld.get("volume"), fld.get("amount"), fld.get("turn"),
                 r.source, now_iso),
            )
        conn.commit()
        rows = conn.execute(
            """SELECT date, open, high, low, close, volume, amount, turnover, source
               FROM kline_cache WHERE symbol = ? AND freq = ?
               ORDER BY date DESC LIMIT ?""",
            (symbol, freq, limit),
        ).fetchall()
        return [_row_to_dict(r) for r in reversed(rows)]

    @staticmethod
    def get_fund_flow(code: str) -> list[dict[str, Any]]:
        """akshare stock_individual_fund_flow_rank — 取该 code 当日。"""
        import akshare as ak
        df = ak.stock_individual_fund_flow_rank(indicator="今日")
        rows = df[df["代码"].astype(str) == code]
        return [
            {"name": str(r["名称"]), "code": str(r["代码"]),
             "close": float(r.get("最新价", 0) or 0),
             "change_pct": float(r.get("涨跌幅", 0) or 0),
             "main_net_inflow": float(r.get("主力净流入-净额", 0) or 0),
             "main_net_inflow_pct": float(r.get("主力净流入-净占比", 0) or 0),
             "super_net_inflow": float(r.get("超大单净流入-净额", 0) or 0),
             "big_net_inflow": float(r.get("大单净流入-净额", 0) or 0),
             "medium_net_inflow": float(r.get("中单净流入-净额", 0) or 0),
             "small_net_inflow": float(r.get("小单净流入-净额", 0) or 0)}
            for _, r in rows.iterrows()
        ]

    @staticmethod
    def get_summary(code: str) -> dict[str, Any]:
        """akshare stock_zh_a_spot_em — 筛 code。"""
        import akshare as ak
        df = ak.stock_zh_a_spot_em()
        rows = df[df["代码"].astype(str) == code]
        if rows.empty:
            return {}
        r = rows.iloc[0]
        return {
            "code": str(r["代码"]),
            "name": str(r["名称"]),
            "close": float(r.get("最新价", 0) or 0),
            "change_pct": float(r.get("涨跌幅", 0) or 0),
            "change": float(r.get("涨跌额", 0) or 0),
            "volume": float(r.get("成交量", 0) or 0),
            "amount": float(r.get("成交额", 0) or 0),
            "amplitude": float(r.get("振幅", 0) or 0),
            "high": float(r.get("最高", 0) or 0),
            "low": float(r.get("最低", 0) or 0),
            "open": float(r.get("今开", 0) or 0),
            "prev_close": float(r.get("昨收", 0) or 0),
            "turnover_rate": float(r.get("换手率", 0) or 0),
            "pe": float(r.get("市盈率-动态", 0) or 0),
            "pb": float(r.get("市净率", 0) or 0),
            "market_cap": float(r.get("总市值", 0) or 0),
            "float_cap": float(r.get("流通市值", 0) or 0),
        }

    # ── 实时 / 分时 ────────────────────────────────────────────
    @staticmethod
    async def get_realtime_batch(codes: list[str]) -> dict[str, dict[str, Any]]:
        """Sina hq.sinajs.cn 批量拉实时报价 (单 HTTP, 多 code 逗号拼接)。
        code 接受 '000001' 或 'sz.000001', 自动补前缀。
        返回: {code: {name, open, prev_close, price, high, low, volume, amount, change, change_pct, time}}
        """
        import httpx
        if not codes:
            return {}
        syms = [_sina_symbol(c) for c in codes]
        url = "https://hq.sinajs.cn/list=" + ",".join(syms)
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(url, headers={"Referer": "https://finance.sina.com.cn"})
            r.raise_for_status()
        except Exception as e:
            log.warning(f"[realtime] fetch failed: {e}")
            return {}
        out: dict[str, dict[str, Any]] = {}
        for sym, raw in re.findall(r'hq_str_([a-z0-9.]+)="([^"]*)";?', r.text):
            if not raw:
                continue
            fields = raw.split(",")
            if len(fields) < 32:
                continue
            try:
                # Sina 符号 sz000001 无点; baostock 风格 sz.000001 兼容
                code6 = sym.split(".", 1)[1] if "." in sym else sym[2:]
                open_ = float(fields[1]) or 0
                prev = float(fields[2]) or 0
                cur = float(fields[3]) or 0
                high = float(fields[4]) or 0
                low = float(fields[5]) or 0
                vol = float(fields[8]) or 0
                amt = float(fields[9]) or 0
                change = cur - prev
                pct = (change / prev * 100) if prev else 0
                out[code6] = {
                    "code": code6,
                    "name": fields[0],
                    "open": open_,
                    "prev_close": prev,
                    "price": cur,
                    "high": high,
                    "low": low,
                    "volume": vol,
                    "amount": amt,
                    "change": round(change, 4),
                    "change_pct": round(pct, 3),
                    "time": f"{fields[30]} {fields[31]}",
                }
            except (ValueError, IndexError) as e:
                log.debug(f"[realtime {sym}] parse skip: {e}")
        return out

    @staticmethod
    async def get_minute(code: str) -> list[dict[str, Any]]:
        """Tencent web.ifzq 分时: 返回 240+ 个 1 分钟 bar (HHMM price volume amount)。
        ponytail: 1 次 HTTP 拿全天, 平均价 = amount / volume * 100 (vol 单位是手)。
        """
        import httpx
        sym = _sina_symbol(code)
        url = f"https://web.ifzq.gtimg.cn/appstock/app/minute/query?code={_sina_symbol(code)}"
        try:
            async with httpx.AsyncClient(timeout=8.0) as client:
                r = await client.get(url)
            r.raise_for_status()
            data = r.json()
        except Exception as e:
            log.warning(f"[minute {code}] fetch failed: {e}")
            return []
        try:
            raw = data["data"][sym]["data"]["data"]
        except (KeyError, TypeError):
            return []
        rows: list[dict[str, Any]] = []
        for line in raw:
            parts = line.split()
            if len(parts) < 4:
                continue
            t, price, vol, amt = parts[0], parts[1], parts[2], parts[3]
            try:
                p = float(price)
                v = float(vol)
                a = float(amt)
                avg = (a / (v * 100)) if v else p  # vol 单位手, 1 手 = 100 股
                rows.append({"time": t, "price": p, "volume": v, "amount": a, "avg_price": round(avg, 3)})
            except ValueError:
                continue
        # ponytail: Tencent API 永远返回"进行中"那根 bar, 比 wall clock 晚 0-60s.
        # 只在交易时段 (09:30-15:00) 截断到当前分钟; 午间/盘后/盘前原样
        now = datetime.now()
        hhmm_now = f"{now.hour:02d}{now.minute:02d}"
        if "0930" <= hhmm_now <= "1500":
            rows = [r for r in rows if r["time"] <= hhmm_now]
        return rows

    @staticmethod
    def get_news(code: str, limit: int = 10) -> list[dict[str, Any]]:
        """akshare stock_news_em — 10 条。"""
        import akshare as ak
        try:
            df = ak.stock_news_em(symbol=code)
        except Exception as e:
            log.warning(f"[stock {code}] news fetch failed: {e}")
            return []
        return [
            {"title": str(r.get("新闻标题", "")), "time": str(r.get("发布时间", "")),
             "source": str(r.get("文章来源", "")), "url": str(r.get("新闻链接", ""))}
            for _, r in df.head(limit).iterrows()
        ]


def _a_share_symbol(code: str) -> str:
    """A 股代码 → baostock 格式 (sh.600000 / sz.000001)。
    600/601/603/605/688 = 沪市; 000/001/002/300 = 深市; 8/4 开头 = 北交所 (sz. 暂用)。
    已带 . 前缀直接返回。
    """
    if "." in code:
        return code
    if code.startswith(("60", "688", "9")):
        return f"sh.{code}"
    return f"sz.{code}"


def _sina_symbol(code: str) -> str:
    """A 股代码 → Sina/Tencent 格式 (sh600000 / sz000001, 紧贴无点)。"""
    if "." in code:
        return code.replace(".", "")
    if code.startswith(("60", "688", "9")):
        return f"sh{code}"
    return f"sz{code}"