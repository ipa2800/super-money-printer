"""全 10 表 DDL — spec §5.2。一次性写齐,后续不再扩 schema。"""
from __future__ import annotations

# ponytail: 全表 IF NOT EXISTS,幂等可重跑
SCHEMA_SQL: list[str] = [
    # K线 (ETF/指数/股票 统一, freq 区分 d/w/m)
    """
    CREATE TABLE IF NOT EXISTS kline_cache (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol      TEXT NOT NULL,
        freq        TEXT NOT NULL,
        date        TEXT NOT NULL,
        open        REAL NOT NULL,
        high        REAL NOT NULL,
        low         REAL NOT NULL,
        close       REAL NOT NULL,
        volume      REAL,
        amount      REAL,
        turnover    REAL,
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        UNIQUE(symbol, freq, date, source)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_kline_symbol_freq ON kline_cache(symbol, freq)",
    "CREATE INDEX IF NOT EXISTS idx_kline_date ON kline_cache(date)",
    # ETF 份额
    """
    CREATE TABLE IF NOT EXISTS shares_cache (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT NOT NULL,
        date        TEXT NOT NULL,
        shares      REAL NOT NULL,
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        UNIQUE(code, date, source)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_shares_code ON shares_cache(code)",
    "CREATE INDEX IF NOT EXISTS idx_shares_date ON shares_cache(date)",
    "CREATE INDEX IF NOT EXISTS idx_shares_source ON shares_cache(source)",
    # 成交量
    """
    CREATE TABLE IF NOT EXISTS volume_cache (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT NOT NULL,
        date        TEXT NOT NULL,
        volume      REAL NOT NULL,
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        UNIQUE(code, date, source)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_volume_code ON volume_cache(code)",
    "CREATE INDEX IF NOT EXISTS idx_volume_date ON volume_cache(date)",
    # 宏观指标
    """
    CREATE TABLE IF NOT EXISTS macro_cache (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        indicator   TEXT NOT NULL,
        date        TEXT NOT NULL,
        value       REAL NOT NULL,
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        UNIQUE(indicator, date, source)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_macro_indicator ON macro_cache(indicator)",
    "CREATE INDEX IF NOT EXISTS idx_macro_date ON macro_cache(date)",
    # 实时行情快照 (东方财富33字段)
    """
    CREATE TABLE IF NOT EXISTS realtime_cache (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        symbol      TEXT NOT NULL,
        symbol_type TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        data        TEXT NOT NULL,
        UNIQUE(symbol, symbol_type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_realtime_symbol ON realtime_cache(symbol)",
    # 缓存元数据
    """
    CREATE TABLE IF NOT EXISTS cache_meta (
        code        TEXT NOT NULL,
        key         TEXT NOT NULL,
        value       TEXT NOT NULL,
        updated_at  TEXT NOT NULL,
        PRIMARY KEY (code, key)
    )
    """,
    # 任务执行记录 (断点续传)
    """
    CREATE TABLE IF NOT EXISTS task_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        task_id     TEXT NOT NULL,
        date        TEXT NOT NULL,
        status      TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        UNIQUE(task_id, date)
    )
    """,
    # 数据源健康状态
    """
    CREATE TABLE IF NOT EXISTS provider_health (
        provider    TEXT NOT NULL PRIMARY KEY,
        status      TEXT NOT NULL,
        last_check  TEXT NOT NULL,
        latency_ms  REAL,
        error_msg   TEXT
    )
    """,
    # 预警记录
    """
    CREATE TABLE IF NOT EXISTS alert_records (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        alert_type  TEXT NOT NULL,
        severity    TEXT NOT NULL,
        source      TEXT NOT NULL,
        message     TEXT NOT NULL,
        detail      TEXT,
        acknowledged INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT NOT NULL,
        UNIQUE(alert_type, source, created_at)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_alert_acknowledged ON alert_records(acknowledged)",
    "CREATE INDEX IF NOT EXISTS idx_alert_created ON alert_records(created_at DESC)",
    # 可配置的刷新任务
    """
    CREATE TABLE IF NOT EXISTS refresh_jobs (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id          TEXT NOT NULL UNIQUE,
        layer           TEXT NOT NULL,
        cron_expr       TEXT NOT NULL,
        enabled         INTEGER NOT NULL DEFAULT 1,
        retry_enabled   INTEGER NOT NULL DEFAULT 1,
        retry_cron_expr TEXT,
        retry_max       INTEGER NOT NULL DEFAULT 1,
        description     TEXT,
        created_at      TEXT NOT NULL,
        updated_at      TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_refresh_jobs_enabled ON refresh_jobs(enabled)",
    # ── Slice 4 新增: 池管理 (ETF / 指数 / 自选股) ──
    """
    CREATE TABLE IF NOT EXISTS etf_pool (
        code        TEXT PRIMARY KEY,
        name        TEXT,
        added_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS index_pool (
        symbol      TEXT PRIMARY KEY,
        name        TEXT,
        added_at    TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS stock_pool (
        code        TEXT PRIMARY KEY,
        name        TEXT,
        added_at    TEXT NOT NULL
    )
    """,
    # provider_health 已存在, 此处复用 — 用于 cache status "failed" 计算
]


def init_schema(conn) -> None:
    """在给定 connection 上跑全部 DDL + seed refresh_jobs 默认 4 行 (若空)。"""
    from datetime import datetime, timezone
    cur = conn.cursor()
    for stmt in SCHEMA_SQL:
        cur.execute(stmt)
    # seed refresh_jobs 默认 4 行 (L0/L1/L2/L3)
    n = cur.execute("SELECT COUNT(*) FROM refresh_jobs").fetchone()[0]
    if n == 0:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        seeds = [
            ("l0_realtime", "L0", "0 * * * *",     0, 0, None,  0, "实时行情轮询(每分钟第0秒)"),
            ("l1_daily",    "L1", "5 16 * * 1-5",  1, 1, "5 17 * * 1-5",  1, "日终结算:K线封存+份额+成交量"),
            ("l2_monthly",  "L2", "30 9 1 * *",    1, 1, "30 10 2 * *",   2, "月初宏观:PMI/M2/CPI/LPR/社融"),
            ("l3_evening",  "L3", "0 18 * * 1-5",  1, 1, "0 19 * * 1-5",  1, "傍晚宏观:主力/国债/SHIBOR/美元"),
        ]
        cur.executemany(
            """INSERT INTO refresh_jobs
               (job_id, layer, cron_expr, enabled, retry_enabled, retry_cron_expr, retry_max, description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(jid, layer, cron, en, re_en, re_cron, re_max, desc, now, now)
             for (jid, layer, cron, en, re_en, re_cron, re_max, desc) in seeds],
        )
    conn.commit()