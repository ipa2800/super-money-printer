"""MacroService — 宏观指标卡片数据。

返回结构 (给前端卡片渲染):
{
  "cards": [
    {"indicator": "mainflow", "name": "主力净流入", "value": -123.4, "unit": "亿元",
     "date": "2026-06-29", "change": -50.2, "change_pct": null,
     "sparkline": [{"date": "2026-06-23", "value": -100}, ...]},
    ...
  ]
}

sparkline 默认最近 30 天 (日频) 或 12 个月 (月频)。
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any, Optional

from backend.db.connection import get_connection
from backend.providers.base import FetchResult
from backend.providers.registry import get_registry

log = logging.getLogger(__name__)


# 卡片定义: indicator → 显示名/单位/类型(D/M)/sparkline长度
CARD_DEFS = [
    {"indicator": "mainflow",  "name": "主力净流入", "unit": "亿元", "freq": "D", "spark": 30, "decimals": 2},
    {"indicator": "bond_10y",  "name": "10年国债",   "unit": "%",    "freq": "D", "spark": 30, "decimals": 3},
    {"indicator": "usd_cny",   "name": "美元/人民币","unit": "",     "freq": "D", "spark": 30, "decimals": 4},
    {"indicator": "shibor_on", "name": "SHIBOR隔夜", "unit": "%",    "freq": "D", "spark": 30, "decimals": 3},
    {"indicator": "pmi_mfg",   "name": "制造业PMI",  "unit": "",     "freq": "M", "spark": 12, "decimals": 1},
    {"indicator": "m2",        "name": "M2同比",     "unit": "%",    "freq": "M", "spark": 12, "decimals": 2},
    {"indicator": "cpi",       "name": "CPI同比",    "unit": "%",    "freq": "M", "spark": 12, "decimals": 2},
    {"indicator": "lpr_1y",    "name": "LPR 1Y",     "unit": "%",    "freq": "M", "spark": 12, "decimals": 3},
]


def _row_to_dict(row) -> dict:
    return {k: row[k] for k in row.keys()}


class MacroService:
    def __init__(self) -> None:
        self.registry = get_registry()

    async def get_cards(self) -> dict[str, Any]:
        """获取所有宏观卡片: 最新值 + sparkline + 前一日变化。"""
        cards = await asyncio.gather(
            *(self._card_for(def_) for def_ in CARD_DEFS),
            return_exceptions=False,
        )
        return {"cards": cards}

    async def _card_for(self, def_: dict) -> dict:
        indicator = def_["indicator"]
        # lpr 是个特殊情况, indicator 实际是 'lpr', 字段是 lpr_1y
        cache_indicator = "lpr" if indicator == "lpr_1y" else indicator

        # 1) 查 DB
        conn = get_connection()
        rows = conn.execute(
            """
            SELECT date, value FROM macro_cache
            WHERE indicator = ?
            ORDER BY date DESC
            LIMIT ?
            """,
            (cache_indicator, def_["spark"]),
        ).fetchall()
        rows = list(reversed(rows))  # 升序

        if len(rows) < max(3, def_["spark"] // 4):
            # 数据不够 → 拉网络, 写库
            await self._refresh_from_network(cache_indicator, def_)
            rows = conn.execute(
                """
                SELECT date, value FROM macro_cache
                WHERE indicator = ?
                ORDER BY date DESC
                LIMIT ?
                """,
                (cache_indicator, def_["spark"]),
            ).fetchall()
            rows = list(reversed(rows))

        if not rows:
            return {
                "indicator": indicator,
                "name": def_["name"],
                "value": None,
                "unit": def_["unit"],
                "date": None,
                "change": None,
                "sparkline": [],
                "decimals": def_["decimals"],
            }

        # 2) 提取最新值 + 计算变化
        latest = _row_to_dict(rows[-1])
        prev = _row_to_dict(rows[-2]) if len(rows) >= 2 else None

        # LPR 特殊: 用 lpr_1y 字段而不是 value
        if indicator == "lpr_1y":
            latest_lpr_row = conn.execute(
                "SELECT date, value FROM macro_cache WHERE indicator='lpr' ORDER BY date DESC LIMIT 1"
            ).fetchone()
            if latest_lpr_row:
                # 取最近一行的 lpr_1y 字段
                # 实际: lpr 是 dict in raw_data, 简单做法: 把 lpr 1Y 单独处理
                pass

        value = latest["value"]
        if indicator == "usd_cny" and value:
            value = round(value, 4)
        elif def_["decimals"] is not None and value is not None:
            value = round(value, def_["decimals"])

        change = None
        if prev and prev["value"] is not None and value is not None:
            change = round(value - prev["value"], def_["decimals"])

        sparkline = [
            {"date": r["date"], "value": (round(r["value"], 4) if indicator == "usd_cny" else r["value"])}
            for r in rows
        ]

        return {
            "indicator": indicator,
            "name": def_["name"],
            "value": value,
            "unit": def_["unit"],
            "date": latest["date"],
            "change": change,
            "sparkline": sparkline,
            "decimals": def_["decimals"],
        }

    async def _refresh_from_network(self, indicator: str, def_: dict) -> None:
        """从网络拉并写库。"""
        primary = self.registry.get_primary(indicator)
        if primary is None:
            log.warning(f"[macro] no provider for {indicator}")
            return
        # 范围: 日频 spark 天, 月频 14 个月
        date_to = date.today()
        if def_["freq"] == "M":
            # 14 个月前
            year = date_to.year
            month = date_to.month - 13
            while month <= 0:
                month += 12
                year -= 1
            date_from = date(year, month, 1)
        else:
            date_from = date_to - timedelta(days=def_["spark"] * 2)

        try:
            results: list[FetchResult] = await self.registry.fetch_with_fallback(
                indicator=indicator,
                date_from=date_from,
                date_to=date_to,
            )
        except Exception as e:
            log.warning(f"[macro] fetch {indicator} failed: {e}")
            return

        if not results:
            return

        conn = get_connection()
        cur = conn.cursor()
        now_iso = results[0].fetched_at.isoformat(timespec="seconds")
        for r in results:
            if r.value is None:
                continue
            cur.execute(
                """
                INSERT OR REPLACE INTO macro_cache (indicator, date, value, source, fetched_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (indicator, r.date.isoformat(), float(r.value), r.source, now_iso),
            )
        conn.commit()