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

    # ── 板块分析规则 (l5_sector_analytics 调用) ──
    # 主升浪: RPS_20 >= 80 且 加速度 > 0 (强 + 加速)
    # 资金异常流入: 资金流分位 >= 90 (近20日新高)
    # 龙头确立: 龙头连板 >= 3 且 涨停密度 >= 20%
    async def run_sector_rules(self) -> dict[str, int]:
        """扫 sector_analytics 当日, 触发规则写 alert_records.
        返回 {'main_wave': N, 'flow_anomaly': M, 'leader': K}"""
        from datetime import datetime
        conn = get_connection()
        rows = conn.execute(
            """SELECT a.code, a.type, s.name,
                      a.rps_20, a.accel_5_20, a.net_flow_rank,
                      a.max_continuous, a.limit_up_density
               FROM sector_analytics a
               LEFT JOIN sector_cache s ON a.code=s.code AND a.type=s.type
               WHERE a.date = date('now')"""
        ).fetchall()
        n_main = n_flow = n_leader = 0
        for r in rows:
            sym = f"{r['type']}:{r['code']}"
            name = r["name"] or sym
            # 规则 1: 主升浪
            if (r["rps_20"] or 0) >= 80 and (r["accel_5_20"] or 0) > 0:
                _insert_alert(
                    "sector_main_wave", "yellow", sym,
                    f"主升浪启动: {name} RPS={r['rps_20']:.0f} 加速度={r['accel_5_20']:.2f}",
                    f"code={r['code']} type={r['type']}",
                )
                n_main += 1
            # 规则 2: 资金异常流入
            if (r["net_flow_rank"] or 0) >= 90:
                _insert_alert(
                    "sector_flow_anomaly", "yellow", sym,
                    f"资金异常流入: {name} 净流入分位={r['net_flow_rank']:.0f}/100",
                    f"code={r['code']} type={r['type']}",
                )
                n_flow += 1
            # 规则 3: 龙头确立
            if (r["max_continuous"] or 0) >= 3 and (r["limit_up_density"] or 0) >= 0.20:
                _insert_alert(
                    "sector_leader_set", "red", sym,
                    f"龙头确立: {name} 龙头{r['max_continuous']}连板 涨停密度={r['limit_up_density']*100:.1f}%",
                    f"code={r['code']} type={r['type']}",
                )
                n_leader += 1
        return {"main_wave": n_main, "flow_anomaly": n_flow, "leader": n_leader}

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