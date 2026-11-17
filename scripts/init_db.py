"""初始化数据库: 建 schema + seed refresh_jobs 默认 4 行。"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

# 把项目根加进 sys.path,允许 python scripts/init_db.py 直接跑
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from backend.config import get_settings  # noqa: E402
from backend.db.connection import get_connection  # noqa: E402
from backend.db.schema import init_schema  # noqa: E402


DEFAULT_JOBS = [
    ("l0_realtime",  "L0", "0 * * * *",        1, 0, None,            0, "实时行情轮询(每分钟第0秒)"),
    ("l1_daily",     "L1", "5 16 * * 1-5",     1, 1, "5 17 * * 1-5", 1, "日终结算:K线封存+份额+成交量"),
    ("l2_monthly",   "L2", "30 9 1 * *",       1, 1, "30 10 2 * *",  2, "月初宏观:PMI/M2/CPI/LPR/社融"),
    ("l3_evening",   "L3", "0 18 * * 1-5",     1, 1, "0 19 * * 1-5", 1, "傍晚宏观:主力/国债/SHIBOR/美元"),
]


# ponytail: 8 只主指 — 含首页"指数走势"要的 4 只 + 4 只板块代表。baostock 格式 (sh./sz. 前缀)。
# 首页走势: 上证(sh.000001) / 深证(sz.399001) / 创业板(sz.399006) / 科创50(sh.000688)
# 板块代表: 沪深300(sh.000300) / 上证50(sh.000016) / 中证500(sh.000905) / 中证1000(sh.000852)
DEFAULT_INDICES = [
    ("sh.000001", "上证指数"),
    ("sh.000016", "上证50"),
    ("sh.000300", "沪深300"),
    ("sh.000688", "科创50"),
    ("sh.000852", "中证1000"),
    ("sh.000905", "中证500"),
    ("sz.399001", "深证指数"),
    ("sz.399006", "创业板指"),
]


def seed_refresh_jobs(conn) -> None:
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cur = conn.cursor()
    for job in DEFAULT_JOBS:
        cur.execute(
            """
            INSERT OR IGNORE INTO refresh_jobs
                (job_id, layer, cron_expr, enabled, retry_enabled,
                 retry_cron_expr, retry_max, description, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (*job, now, now),
        )
    conn.commit()


def seed_index_pool(conn) -> None:
    """灌默认 8 只主指 — repeat run 安全 (INSERT OR IGNORE), 已存在的 symbol 跳过。"""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn.executemany(
        "INSERT OR IGNORE INTO index_pool (symbol, name, added_at) VALUES (?, ?, ?)",
        [(sym, name, now) for sym, name in DEFAULT_INDICES],
    )
    conn.commit()


def main() -> None:
    settings = get_settings()
    print(f"DB path: {settings.db_path_resolved}")
    conn = get_connection()
    init_schema(conn)
    seed_refresh_jobs(conn)
    seed_index_pool(conn)
    # 验收: 列出所有表
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(f"Tables ({len(rows)}):")
    for r in rows:
        print(f"  - {r['name']}")
    job_rows = conn.execute("SELECT job_id, layer, cron_expr FROM refresh_jobs").fetchall()
    print(f"refresh_jobs ({len(job_rows)}):")
    for r in job_rows:
        print(f"  - {r['job_id']:14s} {r['layer']} {r['cron_expr']}")


if __name__ == "__main__":
    main()