"""AlertService — 阈值判定 + alert_records 写入。

规则 (MVP, 写死, 后续迁 yaml):
  - bond_10y  | 单日变化 > 0.10%      → yellow
  - mainflow  | 单日变化 > 1000亿      → yellow; > 2000亿 → red
  - usd_cny   | 单日变化 > 0.05        → yellow
  - ETF shares | 单日变化 > 30%       → red
  - provider  | 连续失败 ≥ 5 次        → red (job_failure)
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any

from backend.db.connection import get_connection

log = logging.getLogger(__name__)


# 阈值表
MACRO_THRESHOLDS = {
    "bond_10y":  {"warn": 0.10, "level": "yellow"},
    "mainflow":  {"warn": 1000.0, "critical": 2000.0, "level_above": "yellow", "level_critical": "red"},
    "usd_cny":   {"warn": 0.05, "level": "yellow"},
    "shibor_on": {"warn": 0.50, "level": "yellow"},
    "m2":        {"warn": 1.0,  "level": "yellow"},
    "cpi":       {"warn": 0.5,  "level": "yellow"},
}
ETF_SHARE_DAILY_CHANGE = 0.30  # 30% 单日变化


def _insert_alert(alert_type: str, severity: str, source: str,
                  message: str, detail: str = "") -> None:
    """去重写入 alert_records (UNIQUE alert_type+source+created_at 分钟级)。"""
    from datetime import datetime
    conn = get_connection()
    # 用整分钟去重
    minute = datetime.now().strftime("%Y-%m-%dT%H:%M")
    try:
        conn.execute(
            """
            INSERT INTO alert_records (alert_type, severity, source, message, detail, acknowledged, created_at)
            VALUES (?, ?, ?, ?, ?, 0, ?)
            """,
            (alert_type, severity, source, message, detail, minute),
        )
        conn.commit()
        log.info(f"[alert] new: {severity} {alert_type} {source} — {message}")
    except Exception as e:
        if "UNIQUE" in str(e):
            pass  # 这分钟已经报过了
        else:
            raise


class AlertService:
    def check_macro(self) -> int:
        """扫 macro_cache 最新两天, 触发阈值就写 alert_records。返回写入条数。"""
        n = 0
        conn = get_connection()
        for ind, cfg in MACRO_THRESHOLDS.items():
            rows = conn.execute(
                "SELECT date, value FROM macro_cache WHERE indicator = ? ORDER BY date DESC LIMIT 2",
                (ind,),
            ).fetchall()
            if len(rows) < 2:
                continue
            latest, prev = rows[0], rows[1]
            change = latest["value"] - prev["value"]
            msg = f"{ind} 单日变化 {change:+.3f}"
            if "critical" in cfg and abs(change) >= cfg["critical"]:
                _insert_alert("macro_threshold", cfg["level_critical"], ind, msg, f"prev={prev['value']} latest={latest['value']}")
                n += 1
            elif abs(change) >= cfg["warn"]:
                _insert_alert("macro_threshold", cfg["level"], ind, msg, f"prev={prev['value']} latest={latest['value']}")
                n += 1
        return n

    def check_etf_shares(self) -> int:
        """扫 shares_cache, 单日变化 > 30% 写 alert。"""
        n = 0
        conn = get_connection()
        # 找最近 30 天内每个 code 的最后两个日期
        cutoff = (date.today() - timedelta(days=30)).isoformat()
        rows = conn.execute(
            """
            SELECT code, date, shares FROM shares_cache
            WHERE date >= ?
            ORDER BY code, date DESC
            """,
            (cutoff,),
        ).fetchall()
        # 按 code 分组
        by_code: dict[str, list] = {}
        for r in rows:
            by_code.setdefault(r["code"], []).append(r)
        for code, series in by_code.items():
            if len(series) < 2:
                continue
            latest, prev = series[0], series[1]
            if prev["shares"] == 0:
                continue
            change_pct = abs((latest["shares"] - prev["shares"]) / prev["shares"])
            if change_pct >= ETF_SHARE_DAILY_CHANGE:
                _insert_alert(
                    "etf_threshold", "red", code,
                    f"{code} 份额单日变化 {change_pct*100:.1f}%",
                    f"prev={prev['shares']:.0f} latest={latest['shares']:.0f}",
                )
                n += 1
        return n

    async def run_all_checks(self) -> dict[str, Any]:
        n_macro = self.check_macro()
        n_etf = self.check_etf_shares()
        return {"macro_alerts": n_macro, "etf_alerts": n_etf}

    @staticmethod
    def list_alerts(limit: int = 50, only_unack: bool = False) -> list[dict]:
        conn = get_connection()
        sql = "SELECT * FROM alert_records"
        params: tuple = ()
        if only_unack:
            sql += " WHERE acknowledged = 0"
        sql += " ORDER BY created_at DESC, id DESC LIMIT ?"
        params = (limit,)
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    @staticmethod
    def ack(alert_id: int) -> bool:
        conn = get_connection()
        cur = conn.execute(
            "UPDATE alert_records SET acknowledged = 1 WHERE id = ?",
            (alert_id,),
        )
        conn.commit()
        return cur.rowcount > 0

    @staticmethod
    def get_config() -> dict:
        """返回前端可读的阈值表 — 后续从 yaml 读, 现在硬编码。"""
        return {
            "macro": MACRO_THRESHOLDS,
            "etf_share_daily_change": ETF_SHARE_DAILY_CHANGE,
        }