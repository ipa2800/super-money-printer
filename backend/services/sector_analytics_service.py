"""SectorAnalyticsService — 板块分析层 (4 维度指标计算).

数据流:
  1. refresh_fund_flow        — 拉 sector_fund_flow  (同花顺接口)
  2. refresh_constituents     — 拉 sector_constituents (板块成分股)
  3. refresh_limit_up_pool    — 拉 limit_up_pool      (涨停股池, 日级)
  4. compute_analytics(date)  — 从以上 + sector_history 计算指标写 sector_analytics
  5. get_rank / get_matrix    — 读 sector_analytics 返回排名/象限

核心指标:
  RPS_20       = (20日涨幅排名 / 总数) * 100              欧奈尔
  accel_5_20   = (ret_5d/5) - (ret_20d/20)               正=加速
  net_flow     = 当日净额 (元)
  net_flow_rank = 近 20 日净额排名分位 (0-100)
  limit_up_density = 板块内涨停数 / 成分股数
  max_continuous   = 板块内股票最大连板数
  rank_overall = 0.4*rps_rank + 0.3*accel_rank + 0.2*net_rank + 0.1*limit_density_rank
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta
from typing import Any, Optional

from backend.db.connection import get_connection
from backend.providers.registry import get_registry

log = logging.getLogger(__name__)


# 综合排名权重 (可后期调到 config)
WEIGHTS = {"rps": 0.4, "accel": 0.3, "net_flow": 0.2, "limit_density": 0.1}


def _row_to_dict(row) -> dict[str, Any]:
    return {k: row[k] for k in row.keys()}


class SectorAnalyticsService:
    def __init__(self) -> None:
        self.registry = get_registry()

    # ── 1. 板块资金流 ──
    async def refresh_fund_flow(self, target_date: Optional[date] = None) -> int:
        """拉一次 (同花顺"即时"快照) 写 sector_fund_flow. 返回写入条数."""
        target_date = target_date or date.today()
        results = await self.registry.fetch_with_fallback(
            indicator="sector_fund_flow",
            date_from=target_date,
            date_to=target_date,
        )
        if not results:
            return 0
        # name → code/type 映射 (同花顺接口只给 name, 需 sector_cache 解析)
        conn = get_connection()
        name_map = {
            (r["name"], r["type"]): (r["code"], r["type"])
            for r in conn.execute("SELECT code, type, name FROM sector_cache").fetchall()
        }
        now_iso = datetime.now().isoformat(timespec="seconds")
        cur = conn.cursor()
        n = 0
        for r in results:
            f = r.fields or {}
            name = f.get("name")
            sector_type = f.get("type")
            if not name or sector_type not in ("industry", "concept"):
                continue
            mapping = name_map.get((name, sector_type))
            if not mapping:
                # sector_cache 还没这个板块 — 跳过 (l4_sector 还没跑过)
                continue
            code, stype = mapping
            cur.execute(
                """
                INSERT OR REPLACE INTO sector_fund_flow
                    (code, type, date, inflow, outflow, net, pct_chg, source, fetched_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (code, stype, target_date.isoformat(),
                 f.get("inflow"), f.get("outflow"), f.get("net"),
                 f.get("pct_chg"), r.source, now_iso),
            )
            n += 1
        conn.commit()
        log.info(f"[analytics] fund_flow wrote {n} rows for {target_date}")
        return n

    # ── 2. 板块成分股 ──
    async def refresh_constituents(self, delay_sec: float = 0.2) -> dict[str, int]:
        """对 sector_cache 中所有板块拉成分股, 写 sector_constituents.
        串行 + 小 delay 避免被限. 返回 {'industry': N, 'concept': M} 写入板块数."""
        conn = get_connection()
        sectors = conn.execute(
            "SELECT code, type FROM sector_cache"
        ).fetchall()
        ok = {"industry": 0, "concept": 0}
        fail = 0
        now_iso = datetime.now().isoformat(timespec="seconds")
        cur = conn.cursor()
        for s in sectors:
            symbol = f"{s['type']}:{s['code']}"
            try:
                results = await self.registry.fetch_with_fallback(
                    indicator="sector_constituents",
                    date_from=date.today(),
                    date_to=date.today(),
                    symbol=symbol,
                )
            except Exception as e:
                fail += 1
                log.debug(f"[analytics] constituents fail {symbol}: {e}")
                continue
            if not results:
                continue
            # 全量覆盖: 先删旧的
            cur.execute(
                "DELETE FROM sector_constituents WHERE code=? AND type=?",
                (s["code"], s["type"]),
            )
            for r in results:
                f = r.fields or {}
                cur.execute(
                    """INSERT OR IGNORE INTO sector_constituents
                       (code, type, stock_code, stock_name, refreshed_at)
                       VALUES (?, ?, ?, ?, ?)""",
                    (s["code"], s["type"], f.get("stock_code"), f.get("stock_name"), now_iso),
                )
            ok[s["type"]] = ok.get(s["type"], 0) + 1
            await asyncio.sleep(delay_sec)
        conn.commit()
        log.info(f"[analytics] constituents ok={ok} fail={fail}")
        return ok

    # ── 3. 涨停池 ──
    async def refresh_limit_up_pool(self, target_date: Optional[date] = None) -> int:
        """拉某日涨停股池, 写 limit_up_pool. 周末/节假日返回空 DataFrame → 静默返回 0."""
        target_date = target_date or date.today()
        try:
            results = await self.registry.fetch_with_fallback(
                indicator="limit_up_pool",
                date_from=target_date,
                date_to=target_date,
            )
        except Exception as e:
            log.info(f"[analytics] limit_up_pool fetch failed for {target_date}: {e}")
            return 0
        if not results:
            return 0
        conn = get_connection()
        now_iso = datetime.now().isoformat(timespec="seconds")
        cur = conn.cursor()
        # 覆盖该日所有
        cur.execute("DELETE FROM limit_up_pool WHERE date=?", (target_date.isoformat(),))
        n = 0
        for r in results:
            f = r.fields or {}
            cur.execute(
                """INSERT OR IGNORE INTO limit_up_pool
                   (date, code, name, pct_chg, limit_up_time, continuous, industry, source, fetched_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (target_date.isoformat(), r.symbol, f.get("name"),
                 f.get("pct_chg"), f.get("limit_up_time"), f.get("continuous"),
                 f.get("industry"), r.source, now_iso),
            )
            n += 1
        conn.commit()
        log.info(f"[analytics] limit_up_pool wrote {n} rows for {target_date}")
        return n

    # ── 4. 指标计算 ──
    async def compute_analytics(self, target_date: Optional[date] = None) -> int:
        """从 sector_history + sector_fund_flow + limit_up_pool + sector_constituents
        计算所有板块的指标, 写 sector_analytics. 返回写入条数."""
        target_date = target_date or date.today()

        # 4a. 读所有板块的 60+ 日 history
        conn = get_connection()
        sectors = conn.execute("SELECT code, type FROM sector_cache").fetchall()
        if not sectors:
            log.warning("[analytics] no sectors in cache, run l4_sector first")
            return 0

        # 沪深300 基准收益 (近 60 日)
        benchmark_ret = self._load_benchmark_returns(target_date, periods=[1, 5, 10, 20, 60])

        # 4b. 对每个板块计算动量指标
        rows_by_sector: dict[tuple[str, str], dict[str, Any]] = {}
        for s in sectors:
            key = (s["code"], s["type"])
            hist = conn.execute(
                """SELECT date, close FROM sector_history
                   WHERE code=? AND type=? AND date<=?
                   ORDER BY date DESC LIMIT 70""",
                (s["code"], s["type"], target_date.isoformat()),
            ).fetchall()
            if not hist:
                continue
            closes = [r["close"] for r in hist]   # 最新 → 最旧
            rets = self._compute_returns(closes, periods=[1, 5, 10, 20, 60])
            rows_by_sector[key] = {
                "ret_1d": rets.get(1),
                "ret_5d": rets.get(5),
                "ret_10d": rets.get(10),
                "ret_20d": rets.get(20),
                "ret_60d": rets.get(60),
                "name": s["code"],   # 占位, 后续填充 name
            }

        if not rows_by_sector:
            return 0

        # 4c. RPS_20 分位 (欧奈尔) — 0-100, 越高越强
        ret_20_list = sorted(
            [(k, v["ret_20d"]) for k, v in rows_by_sector.items() if v["ret_20d"] is not None],
            key=lambda x: x[1],
        )
        n_total = len(ret_20_list)
        for rank, (k, _) in enumerate(ret_20_list, start=1):
            rows_by_sector[k]["rps_20"] = (rank / n_total) * 100 if n_total else None
            rows_by_sector[k]["_rps_rank"] = rank / n_total

        # 4d. 动量加速度 (5日均 vs 20日均的差, 正=加速)
        for k, v in rows_by_sector.items():
            r5 = v.get("ret_5d")
            r20 = v.get("ret_20d")
            if r5 is not None and r20 is not None:
                v["accel_5_20"] = (r5 / 5) - (r20 / 20)
            else:
                v["accel_5_20"] = None

        # 4e. 资金流 — 读 sector_fund_flow 当日 + 近 20 日分位
        fund_flow_today = {
            (r["code"], r["type"]): dict(r)
            for r in conn.execute(
                """SELECT code, type, net FROM sector_fund_flow
                   WHERE date=?""",
                (target_date.isoformat(),),
            ).fetchall()
        }
        for k, v in rows_by_sector.items():
            v["net_flow"] = fund_flow_today.get(k, {}).get("net")

        # 近 20 日 net 序列 (用于排名分位)
        net_20d: dict[tuple[str, str], list[float]] = {}
        for s in sectors:
            raws = conn.execute(
                """SELECT net FROM sector_fund_flow
                   WHERE code=? AND type=? AND date<=?
                   ORDER BY date DESC LIMIT 20""",
                (s["code"], s["type"], target_date.isoformat()),
            ).fetchall()
            net_20d[(s["code"], s["type"])] = [r["net"] for r in raws if r["net"] is not None]

        # net_flow_rank: 当日 net 在自身近 20 日的分位 (0-100)
        for k, v in rows_by_sector.items():
            today_net = v.get("net_flow")
            series = net_20d.get(k, [])
            if today_net is not None and series:
                rank = sum(1 for x in series if x <= today_net) / len(series)
                v["net_flow_rank"] = rank * 100
            else:
                v["net_flow_rank"] = None

        # 4f. 涨停密度 + 最大连板
        limit_up_rows = conn.execute(
            """SELECT code, name, continuous, industry FROM limit_up_pool WHERE date=?""",
            (target_date.isoformat(),),
        ).fetchall()
        # 板块代码 → 该板块成分股代码集合
        constituents_map: dict[tuple[str, str], set[str]] = {}
        for r in conn.execute("SELECT code, type, stock_code FROM sector_constituents").fetchall():
            key = (r["code"], r["type"])
            constituents_map.setdefault(key, set()).add(r["stock_code"])

        # name → 涨停股 (匹配方式: 涨停池 stock_code ∈ 板块成分股 stock_code)
        stock_code_to_limitup = {r["code"]: r for r in limit_up_rows}
        for k, v in rows_by_sector.items():
            members = constituents_map.get(k, set())
            in_pool = [stock_code_to_limitup[sc] for sc in members if sc in stock_code_to_limitup]
            v["limit_up_count"] = len(in_pool)
            v["constituents_count"] = len(members)
            if members:
                v["limit_up_density"] = len(in_pool) / len(members)
            else:
                v["limit_up_density"] = None
            v["max_continuous"] = max(
                (lu["continuous"] or 0 for lu in in_pool),
                default=None,
            )

        # 4g. 综合排名 (分位混合)
        # 各维度先算自身排名分位
        for col in ("accel_5_20", "net_flow_rank", "limit_up_density"):
            vals = sorted(
                [(k, v.get(col)) for k, v in rows_by_sector.items() if v.get(col) is not None],
                key=lambda x: x[1],
            )
            for rank, (k, _) in enumerate(vals, start=1):
                rows_by_sector[k][f"_{col}_rank"] = rank / len(vals) if vals else None

        for k, v in rows_by_sector.items():
            score = 0.0
            total_w = 0.0
            for dim, col in [
                ("rps", "_rps_rank"),
                ("accel", "_accel_5_20_rank"),
                ("net_flow", "_net_flow_rank_rank"),
                ("limit_density", "_limit_up_density_rank"),
            ]:
                rank_val = v.get(col)
                if rank_val is not None:
                    score += WEIGHTS[dim] * rank_val * 100
                    total_w += WEIGHTS[dim]
            v["rank_overall"] = score / total_w if total_w > 0 else None

        # 4h. 写 sector_analytics (覆盖当日)
        now_iso = datetime.now().isoformat(timespec="seconds")
        cur = conn.cursor()
        cur.execute("DELETE FROM sector_analytics WHERE date=?", (target_date.isoformat(),))
        n = 0
        for (code, stype), v in rows_by_sector.items():
            cur.execute(
                """INSERT OR REPLACE INTO sector_analytics
                   (date, code, type, ret_1d, ret_5d, ret_10d, ret_20d, ret_60d,
                    rps_20, accel_5_20, net_flow, net_flow_rank,
                    limit_up_count, constituents_count, limit_up_density, max_continuous,
                    rank_overall, computed_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (target_date.isoformat(), code, stype,
                 v.get("ret_1d"), v.get("ret_5d"), v.get("ret_10d"), v.get("ret_20d"), v.get("ret_60d"),
                 v.get("rps_20"), v.get("accel_5_20"),
                 v.get("net_flow"), v.get("net_flow_rank"),
                 v.get("limit_up_count"), v.get("constituents_count"),
                 v.get("limit_up_density"), v.get("max_continuous"),
                 v.get("rank_overall"), now_iso),
            )
            n += 1
        conn.commit()
        log.info(f"[analytics] wrote {n} rows for {target_date}")
        return n

    # ── 5. 排名查询 ──
    def get_rank(
        self,
        target_date: Optional[date] = None,
        sort_by: str = "rank_overall",
        limit: int = 50,
        sector_type: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """返回指定日期的板块排名. sort_by ∈ rank_overall|rps_20|accel_5_20|net_flow_rank|limit_up_density."""
        target_date = target_date or date.today()
        valid_cols = {"rank_overall", "rps_20", "accel_5_20", "net_flow_rank", "limit_up_density"}
        if sort_by not in valid_cols:
            sort_by = "rank_overall"
        conn = get_connection()
        # ponytail: 指定日期无数据时回退到最近 ≤ target_date 的数据 (l5 因 akshare crash 可能当天没跑)
        latest = conn.execute(
            """SELECT date FROM sector_analytics
               WHERE date<=? ORDER BY date DESC LIMIT 1""",
            (target_date.isoformat(),),
        ).fetchone()
        if not latest:
            return []
        eff_date = latest["date"]
        if sector_type in ("industry", "concept"):
            rows = conn.execute(
                f"""SELECT a.code, a.type, s.name, s.leader, s.leader_pct, s.price,
                           a.ret_1d, a.ret_5d, a.ret_10d, a.ret_20d, a.ret_60d,
                           a.rps_20, a.accel_5_20,
                           a.net_flow, a.net_flow_rank,
                           a.limit_up_count, a.constituents_count, a.limit_up_density,
                           a.max_continuous, a.rank_overall
                    FROM sector_analytics a
                    LEFT JOIN sector_cache s ON a.code=s.code AND a.type=s.type
                    WHERE a.date=? AND a.type=?
                    ORDER BY a.{sort_by} DESC NULLS LAST
                    LIMIT ?""",
                (eff_date, sector_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                f"""SELECT a.code, a.type, s.name, s.leader, s.leader_pct, s.price,
                           a.ret_1d, a.ret_5d, a.ret_10d, a.ret_20d, a.ret_60d,
                           a.rps_20, a.accel_5_20,
                           a.net_flow, a.net_flow_rank,
                           a.limit_up_count, a.constituents_count, a.limit_up_density,
                           a.max_continuous, a.rank_overall
                    FROM sector_analytics a
                    LEFT JOIN sector_cache s ON a.code=s.code AND a.type=s.type
                    WHERE a.date=?
                    ORDER BY a.{sort_by} DESC NULLS LAST
                    LIMIT ?""",
                (eff_date, limit),
            ).fetchall()
        return [_row_to_dict(r) for r in rows]

    # ── 6. 轮动矩阵 ──
    def get_matrix(self, target_date: Optional[date] = None) -> dict[str, list[dict[str, Any]]]:
        """返回 4 象限分组. 阈值: RPS>=70 强, <30 弱; accel>0 加速, <=0 减速."""
        target_date = target_date or date.today()
        conn = get_connection()
        # ponytail: 同 get_rank — 无数据时回退到最近 ≤ target_date 的日期
        latest = conn.execute(
            """SELECT date FROM sector_analytics
               WHERE date<=? ORDER BY date DESC LIMIT 1""",
            (target_date.isoformat(),),
        ).fetchone()
        if not latest:
            return {"主升浪": [], "顶部": [], "反弹": [], "杀跌": []}
        eff_date = latest["date"]
        rows = conn.execute(
            """SELECT a.code, a.type, s.name,
                      a.rps_20, a.accel_5_20, a.rank_overall
               FROM sector_analytics a
               LEFT JOIN sector_cache s ON a.code=s.code AND a.type=s.type
               WHERE a.date=?""",
            (eff_date,),
        ).fetchall()
        result = {
            "主升浪": [],   # 强 + 加速
            "顶部":   [],   # 强 + 减速
            "反弹":   [],   # 弱 + 加速
            "杀跌":   [],   # 弱 + 减速
        }
        for r in rows:
            d = _row_to_dict(r)
            rps = d.get("rps_20") or 0
            accel = d.get("accel_5_20") or 0
            if rps >= 70:
                if accel > 0:
                    result["主升浪"].append(d)
                else:
                    result["顶部"].append(d)
            else:
                if accel > 0:
                    result["反弹"].append(d)
                else:
                    result["杀跌"].append(d)
        # 各象限按 rank_overall 降序
        for k in result:
            result[k].sort(key=lambda x: x.get("rank_overall") or 0, reverse=True)
        return result

    # ── 综合调度 ──
    async def refresh_all(self, target_date: Optional[date] = None) -> dict[str, int]:
        """一次跑完 fund_flow + constituents + limit_up_pool + analytics.
        返回 {'fund_flow': N, 'constituents_industry': N, 'constituents_concept': M,
              'limit_up_pool': L, 'analytics': A}."""
        target_date = target_date or date.today()
        n_ff = await self.refresh_fund_flow(target_date)
        cc = await self.refresh_constituents()
        n_lup = await self.refresh_limit_up_pool(target_date)
        n_a = await self.compute_analytics(target_date)
        return {
            "fund_flow": n_ff,
            "constituents_industry": cc.get("industry", 0),
            "constituents_concept": cc.get("concept", 0),
            "limit_up_pool": n_lup,
            "analytics": n_a,
        }

    # ── helpers ──
    @staticmethod
    def _compute_returns(closes_desc: list[float], periods: list[int]) -> dict[int, Optional[float]]:
        """closes_desc: 最新 → 最旧. returns[N] = (close[-1] / close[-N-1] - 1) * 100."""
        if not closes_desc:
            return {p: None for p in periods}
        latest = closes_desc[0]
        out = {}
        for p in periods:
            if len(closes_desc) > p and closes_desc[p] not in (None, 0):
                out[p] = (latest / closes_desc[p] - 1) * 100
            else:
                out[p] = None
        return out

    def _load_benchmark_returns(self, target_date: date, periods: list[int]) -> dict[int, Optional[float]]:
        """读沪深300 (sh.000300) 60 日 close, 算各周期收益. 失败返回 None (前端忽略)."""
        try:
            # 走现有 index provider (baostock 优先)
            conn = get_connection()
            rows = conn.execute(
                """SELECT date, close FROM kline_cache
                   WHERE symbol='sh.000300' AND freq='d' AND date<=?
                   ORDER BY date DESC LIMIT 70""",
                (target_date.isoformat(),),
            ).fetchall()
            if rows:
                closes = [r["close"] for r in rows]
                return self._compute_returns(closes, periods)
        except Exception as e:
            log.debug(f"[analytics] benchmark load failed: {e}")
        return {p: None for p in periods}