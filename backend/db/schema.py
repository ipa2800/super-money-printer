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
    # ── Slice 5 新增: 板块/概念 (行业 + 概念) ──
    """
    CREATE TABLE IF NOT EXISTS sector_cache (
        code        TEXT NOT NULL,
        type        TEXT NOT NULL,                  -- 'industry' | 'concept'
        name        TEXT NOT NULL,
        price       REAL,
        change      REAL,
        pct_chg     REAL,
        total_mv    REAL,                          -- 总市值 (元)
        turnover    REAL,                          -- 换手率 %
        up_count    INTEGER,                       -- 上涨家数
        down_count  INTEGER,                       -- 下跌家数
        leader      TEXT,                          -- 领涨股票
        leader_pct  REAL,                          -- 领涨股票 涨跌幅
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        PRIMARY KEY (code, type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sector_type ON sector_cache(type)",
    "CREATE INDEX IF NOT EXISTS idx_sector_pct ON sector_cache(pct_chg DESC)",
    """
    CREATE TABLE IF NOT EXISTS sector_history (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        code        TEXT NOT NULL,
        type        TEXT NOT NULL,
        date        TEXT NOT NULL,
        open        REAL NOT NULL,
        close       REAL NOT NULL,
        high        REAL NOT NULL,
        low         REAL NOT NULL,
        volume      REAL,
        amount      REAL,
        pct_chg     REAL,
        change      REAL,
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        UNIQUE(code, type, date, source)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sector_hist_code ON sector_history(code, type)",
    "CREATE INDEX IF NOT EXISTS idx_sector_hist_date ON sector_history(date)",
    # ── 板块分析 (Slice 6): 资金流 + 成分股 + 涨停池 + 预计算指标 ──
    # 板块资金流 (同花顺接口, 每日快照)
    """
    CREATE TABLE IF NOT EXISTS sector_fund_flow (
        code        TEXT NOT NULL,
        type        TEXT NOT NULL,
        date        TEXT NOT NULL,
        inflow      REAL,
        outflow     REAL,
        net         REAL,
        pct_chg     REAL,
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        PRIMARY KEY (code, type, date)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sff_date ON sector_fund_flow(date)",
    # 板块 → 成分股映射 (板块内涨停密度计算)
    """
    CREATE TABLE IF NOT EXISTS sector_constituents (
        code        TEXT NOT NULL,
        type        TEXT NOT NULL,
        stock_code  TEXT NOT NULL,
        stock_name  TEXT,
        refreshed_at TEXT NOT NULL,
        PRIMARY KEY (code, type, stock_code)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sc_stock ON sector_constituents(stock_code)",
    # 涨停池 (每日快照, 用于龙头连板 + 涨停密度)
    """
    CREATE TABLE IF NOT EXISTS limit_up_pool (
        date        TEXT NOT NULL,
        code        TEXT NOT NULL,
        name        TEXT NOT NULL,
        pct_chg     REAL,
        limit_up_time TEXT,
        continuous  INTEGER,
        industry    TEXT,
        source      TEXT NOT NULL,
        fetched_at  TEXT NOT NULL,
        PRIMARY KEY (date, code)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_lup_date ON limit_up_pool(date)",
    # 板块分析快照 (RPS / 加速度 / 资金流分位 / 涨停密度 — 每日预计算)
    """
    CREATE TABLE IF NOT EXISTS sector_analytics (
        date            TEXT NOT NULL,
        code            TEXT NOT NULL,
        type            TEXT NOT NULL,
        ret_1d          REAL,
        ret_5d          REAL,
        ret_10d         REAL,
        ret_20d         REAL,
        ret_60d         REAL,
        rps_20          REAL,
        accel_5_20      REAL,
        net_flow        REAL,
        net_flow_rank   REAL,
        limit_up_count  INTEGER,
        constituents_count INTEGER,
        limit_up_density REAL,
        max_continuous  INTEGER,
        rank_overall    REAL,
        computed_at     TEXT NOT NULL,
        PRIMARY KEY (date, code, type)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_sa_date ON sector_analytics(date)",
    "CREATE INDEX IF NOT EXISTS idx_sa_rank ON sector_analytics(date, rank_overall DESC)",
    # ── 数据日志 (provider fetch + scheduler job 双层追踪) ──
    """
    CREATE TABLE IF NOT EXISTS data_log (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        ts          TEXT NOT NULL,
        layer       TEXT NOT NULL,        -- 'provider' | 'job'
        source      TEXT NOT NULL,        -- 'akshare' / 'eastmoney' / 'job:l5_sector_analytics' / ...
        operation   TEXT,                 -- 'fetch_with_fallback:etf_realtime' / ...
        status      TEXT NOT NULL,        -- 'success' | 'fail'
        level       TEXT NOT NULL,        -- 'info' | 'warn' | 'error'
        latency_ms  INTEGER,
        rows        INTEGER,
        error       TEXT                  -- 失败信息 (截 500 字符)
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_datalog_ts ON data_log(ts DESC)",
    "CREATE INDEX IF NOT EXISTS idx_datalog_source_status ON data_log(source, status)",
    "CREATE INDEX IF NOT EXISTS idx_datalog_layer ON data_log(layer)",
    # provider_health 已存在, 此处复用 — 用于 cache status "failed" 计算
]


def init_schema(conn) -> None:
    """在给定 connection 上跑全部 DDL + seed refresh_jobs 默认 4 行 (若空)。"""
    from datetime import datetime, timezone
    cur = conn.cursor()
    for stmt in SCHEMA_SQL:
        cur.execute(stmt)
    # seed refresh_jobs 默认 6 行 (L0/L1/L2/L3/L4/L5)
    n = cur.execute("SELECT COUNT(*) FROM refresh_jobs").fetchone()[0]
    if n == 0:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        seeds = [
            ("l0_realtime", "L0", "0 * * * *",     0, 0, None,  0, "实时行情轮询(每分钟第0秒)"),
            ("l1_daily",    "L1", "5 16 * * 1-5",  1, 1, "5 17 * * 1-5",  1, "日终结算:K线封存+份额+成交量"),
            ("l2_monthly",  "L2", "30 9 1 * *",    1, 1, "30 10 2 * *",   2, "月初宏观:PMI/M2/CPI/LPR/社融"),
            ("l3_evening",  "L3", "0 18 * * 1-5",  1, 1, "0 19 * * 1-5",  1, "傍晚宏观:主力/国债/SHIBOR/美元"),
            ("l4_sector",   "L4", "30 2 * * *",    1, 1, "0 3 * * *",     2, "板块/概念:快照+全量历史(隔夜)"),
            ("l5_sector_analytics", "L5", "30 16 * * 1-5", 1, 1, "0 17 * * 1-5", 2, "板块分析:RPS/资金流/涨停密度(收市后)"),
        ]
        cur.executemany(
            """INSERT INTO refresh_jobs
               (job_id, layer, cron_expr, enabled, retry_enabled, retry_cron_expr, retry_max, description, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [(jid, layer, cron, en, re_en, re_cron, re_max, desc, now, now)
             for (jid, layer, cron, en, re_en, re_cron, re_max, desc) in seeds],
        )
    conn.commit()