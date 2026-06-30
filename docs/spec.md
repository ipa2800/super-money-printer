# ETF Dashboard 重构技术规格文档

> 本文档为现有 ETF Dashboard (`/Users/peggy/.openclaw/workspace-padiya/scripts/etf_dashboard/`) 重构为 `super-money-printer` 的技术规格说明。

---

## 一、项目定位与目标

**核心目标**：将现有的单体 ETF 监控系统重构为模块化、多数据源、高稳定性的数据基础设施，在保持前端 UI 风格不变的前提下，彻底解决底层数据获取和更新机制的稳定性问题。

**非目标**：不改变现有 UI 视觉风格和交互体验，不重新设计图表组件的渲染逻辑。

---

## 二、现状分析

### 2.1 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3 / FastAPI / uvicorn |
| 数据源 | akshare（主要）+ 直接 HTTP（SSE/SZSE/Tencent） |
| 数据库 | SQLite3（`etf_data.db` ~3MB） |
| 前端 | 原生 JS + ECharts 5 + Tailwind CSS（单文件 ~2500 行） |
| 字体 | Inter（本地 TTF）+ 系统 PingFang/微软雅黑 |
| 部署 | conda + nohup，本地运行 |

### 2.2 现有功能模块

| 模块 | 描述 |
|------|------|
| **看板主页** | 状态横幅、宏观卡片×6、份额走势图、单日申赎图、指数K线、成交量监控、告警面板、ETF数据表 |
| **告警中心** | 当前触发告警列表 |
| **宏观温度计** | ~~综合评分(0-100)、七维指标卡、历史趋势图~~ （重构中暂时搁置，参考代码可复用但效果待验证） |
| **宏观择时** | ~~三层评分体系（政策30%/基本面40%/估值30%）、仓位建议~~ （重构中暂时搁置） |
| **个股分析** | 自选股列表、K线+均线、资金流向，新闻 |
| **数据管理** | ETF增删、缓存管理（刷新/回填/清空）、指数管理 |

### 2.3 数据源架构（实测确定）

#### 2.3.1 Provider 角色定位

| Provider | 数据源 | 定位 | 实测支持 |
|---------|--------|------|---------|
| **BaostockProvider** | `baostock.com` | ⭐ **K线主数据源**（ETF/指数/股票通用） | 日/周/月三频率，含换手率 |
| **SSEProvider** | `query.sse.com.cn` | ⭐ **ETF份额主数据源**（上交所） | 约20+交易日历史 |
| **SZSEProvider** | `fund.szse.cn` | **ETF份额快照**（深交所，仅今日） | 无历史数据 |
| **AkShareProvider** | `akshare`（多接口） | ⭐ **宏观指标 + 实时行情主数据源** | 含33字段/IOPV/资金流 |
| **TushareProvider** | `tushare.pro` | **K线/份额 备选数据源** | 需token，字段全 |
| **EMProvider** | `eastmoney.com` | **实时行情/资金流 备选** | 同AkShare东方财富接口 |
| **TencentProvider** | `web.ifzq.gtimg.cn` | **指数K线 备选** | 直接HTTP |

#### 2.3.2 指标 → 主/备数据源（实测确定）

| 指标 | 主数据源 | 备选1 | 备选2 | 备注 |
|------|---------|--------|--------|------|
| **ETF 份额（上交所）** | SSEProvider | AkShare fund_etf_scale_sse | Tushare | |
| **ETF 份额（深交所）** | SZSEProvider（仅今日） | Tushare | — | |
| **K线 日线（ETF/指数/股票）** | BaostockProvider | AkShare fund_etf_hist_sina | Tushare | |
| **K线 周线** | BaostockProvider | Tushare | — | |
| **K线 月线** | BaostockProvider | Tushare | — | |
| **ETF 实时行情（33字段）** | AkShare fund_etf_spot_em | EMProvider | — | |
| **股票 实时行情** | AkShare stock_zh_a_spot_em | EMProvider | — | |
| **主力净流入** | AkShare `stock_market_fund_flow` | — | — | 关键字段：主力净流入-净额；EM推送接口被代理阻断时无备份 |
| **10年国债** | AkShare `bond_zh_us_rate` | `bond_china_yield`（仅到2021-01-22，过期5年，参考用） | — | 关键字段：中国国债收益率10年 |
| **SHIBOR隔夜** | AkShare `macro_china_shibor_all` | — | — | 关键字段：O/N-定价；无可靠备份 |
| **美元/人民币** | AkShare `currency_boc_safe` | `currency_boc_sina`（历史仅到2023-11） | — | 关键字段：美元；BOC数据×100后÷100转为真实汇率 |
| **PMI** | AkShare `macro_china_pmi` | — | — | 关键字段：制造业-指数；月频，无备份 |
| **M2** | AkShare `macro_china_money_supply` | `macro_china_m2_yearly` | — | 关键字段：货币和准货币(M2)-同比增长；两者数据一致，可互备 |
| **CPI** | AkShare `macro_china_cpi` | `macro_china_cpi_monthly`（1996年起） | — | 关键字段：全国-同比增长；月频 |
| **LPR** | AkShare `macro_china_lpr` | — | — | 关键字段：LPR1Y/LPR5Y；无可靠备份 |
| **社融** | AkShare `macro_china_new_financial_credit` | — | — | 关键字段：当月-同比增长；`macro_china_shrzgm`（商务部）SSL不可用，无备份 |
| **指数K线** | BaostockProvider（d/w/m） | TencentProvider（仅d） | AkShare | |
| **个股资金流/新闻** | AkShare 各模块 | — | — | |
| **行业板块K线** | AkShare `index_hist_sw`（申万，日/周/月） | 同花顺（仅日） | 东财（备，日/周/月，代理阻断时不可用） | 详见 §2.3.4 |
| **概念板块K线** | AkShare 同花顺（仅日线） | 东财（备，日/周/月，代理阻断时不可用） | — | 详见 §2.3.4 |

#### 2.3.3 各 Provider 实测字段能力

| Provider | K线频率 | 换手率 | IOPV | 资金流向 | 份额历史 | 备注 |
|---------|---------|--------|------|---------|---------|------|
| Baostock | d/w/m ✅ | turn ✅ | ❌ | ❌ | ❌ | 需 baostock.login() |
| SSE官方 | — | — | — | — | ~20日 ✅ | 仅上交所 |
| SZSE官方 | — | — | — | — | 今日快照 ❌ | 仅深交所 |
| AkShare-EM | — | ✅ | ✅ | ✅ | ✅ | 东方财富实时接口（EM推送接口可能被代理阻断） |
| AkShare-Sina | d ✅ | — | — | — | — | fund_etf_hist_sina |
| AkShare-宏观 | — | — | — | — | — | 10年国债/SHIBOR/PMI/M2/CPI/LPR/社融/美元 |
| Tushare | d/w/m ✅ | ✅ | ✅ | ✅ | ✅ | 需token |
| Tencent | d ✅ | — | — | — | — | 指数K线 |
| AkShare-申万 | 日/周/月 ✅ | — | — | — | — | `index_hist_sw` 申万行业指数，L1×31 + L2×131 |
| AkShare-同花顺 | 日 ✅ | — | — | — | — | 行业×90 + 概念×361，日线；周/月需手动 resample |
| AkShare-东财 | 日/周/月 ✅ | — | — | — | — | 行业/概念K线，代理阻断时不可用 |

#### 2.3.4 板块K线数据（实测确定，待实现）

> 功能尚未纳入 Phase 计划，后续开发时参考本节。

**板块类型**：

| 类型 | 数据源 | 函数 | 日 | 周 | 月 | 历史深度 | 覆盖数量 |
|------|--------|------|-----|-----|-----|---------|---------|
| **申万行业指数** | AkShare | `index_hist_sw(symbol, period)` | ✅ | ✅ | ✅ | 1999年至今 | L1×31 + L2×131 |
| **同花顺行业板块** | AkShare | `stock_board_industry_index_ths(symbol, start_date, end_date)` | ✅ | ❌ | ❌ | ~5年 | ~90个 |
| **同花顺概念板块** | AkShare | `stock_board_concept_index_ths(symbol, start_date, end_date)` | ✅ | ❌ | ❌ | ~5年 | ~361个 |
| **东财行业/概念K线** | AkShare | `stock_board_industry_hist_em` / `stock_board_concept_hist_em(symbol, period)` | ✅ | ✅ | ✅ | 待测 | 待测 |

**申万行业指数代码查询**：

```python
# L1 一级行业（31个）
ak.sw_index_first_info()  # 返回 code + name

# L2 二级行业（131个）
ak.sw_index_second_info()  # 返回 code + name

# L3 三级行业
ak.sw_index_third_info()

# 调用示例
ak.index_hist_sw(symbol="801030", period="day")   # 日线
ak.index_hist_sw(symbol="801030", period="week")   # 周线
ak.index_hist_sw(symbol="801030", period="month")   # 月线
```

**返回字段**：

```python
# index_hist_sw 返回
["代码", "日期", "收盘", "开盘", "最高", "最低", "成交量", "成交额"]
```

**周/月线实现（同花顺/概念板块）**：

由于同花顺接口仅支持日线，周线和月线通过 pandas resample 实现：

```python
daily = ak.stock_board_concept_index_ths(symbol="半导体", start_date="20200101", end_date="20260629")
daily["日期"] = pd.to_datetime(daily["日期"])
daily = daily.set_index("日期").sort_index()
weekly = daily.resample("W").agg({...}).dropna()    # 周K
monthly = daily.resample("ME").agg({...}).dropna()  # 月K
```

**实现规划（待纳入 Phase 计划）**：

```
SectorProvider (新增 Provider)
  ├── 行业板块K线（日/周/月）
  │   ├── 主：index_hist_sw（申万，L1/L2/L3）
  │   └── 备：东财 stock_board_industry_hist_em（代理恢复后）
  └── 概念板块K线（日/周/月）
      ├── 主：stock_board_concept_index_ths（同花顺，日线）
      ├── 备：东财 stock_board_concept_hist_em（日/周/月）
      └── 周/月：pandas resample from daily
```

### 2.4 数据刷新策略（实测 + 实测确定）

#### 2.4.1 四层刷新架构

```
L0 实时层  ──── 市场时段 30s轮询 ──── K线当日数据、实时行情快照
L1 日终层  ──── 每日 16:05          ──── ETF份额、成交量、K线封存
L2 月初层  ──── 每月1日 09:30      ──── PMI/M2/CPI/LPR/社融
L3 傍晚层  ──── 每日 18:00          ──── 主力净流入/国债/SHIBOR/美元
```

#### 2.4.2 各数据类型的刷新策略

| 数据类型 | 存储表 | 刷新时机 | 触发方式 | TTL | 数据源 |
|---------|--------|---------|---------|-----|--------|
| **K线（日线）** | kline_cache | 市场收盘后 16:05 | L1定时 + **手动API** + **失败重试** | 永久（append-only） | Baostock（主）/ Sina（备） |
| **K线（周/月线）** | kline_cache | K线封存后一次性写入 | L1日终层 | 永久 | Baostock |
| **实时行情（33字段）** | realtime_cache | 市场时段每30s轮询 | L0轮询 + **手动API** | 30s，盘中实时 | AkShare-EM |
| **ETF份额（上交所）** | shares_cache | 每日 16:05 | L1定时 + **手动API** + **失败重试** | 永久 | SSEProvider |
| **ETF份额（深交所）** | shares_cache | 每日 16:05 | L1定时 + **手动API** + **失败重试** | 永久 | SZSEProvider |
| **成交量** | volume_cache | 每日 16:05 | L1定时 + **手动API** | 永久 | Baostock |
| **主力净流入** | macro_cache | 每日 18:00 | L3定时 + **手动API** + **失败重试** | 永久 | AkShare |
| **10年国债/SHIBOR/美元** | macro_cache | 每日 18:00 | L3定时 + **手动API** + **失败重试** | 永久 | AkShare |
| **PMI / M2 / CPI / LPR / 社融** | macro_cache | 每月1日 09:30 | L2定时 + **手动API** + **失败重试** | 永久（按月覆盖） | AkShare |

> **手动API**：任意 Job 均支持 `POST /api/scheduler/jobs/{job_id}/run` 手动触发，不影响定时执行。
> **失败重试**：每个 Job 可配置「失败后自动重试」，最大重试次数和重试时间均可配置。

#### 2.4.3 市场时段判定

- **A股交易日**：周一~周五，剔除交易所公布的节假日
- **市场时段**：`09:30 < now < 16:00`
- **实盘判断**：L0 实时层仅在市场时段运行；非市场时段实时层暂停，realtime_cache 保留最后收盘快照

#### 2.4.4 刷新计划可配置

所有定时刷新计划存储在 `refresh_jobs` 表中，可通过数据管理页面 API 动态修改：
- cron 表达式（如 `5 16 * * 1-5` = 每周一到周五 16:05）
- 启用/禁用状态
- 失败重试策略（重试 cron、最大重试次数）
- 不再写死在代码里，修改后立即生效无需重启

#### 2.4.5 缓存 TTL 策略

| 缓存表 | 正常TTL | 强制刷新条件 |
|--------|---------|------------|
| kline_cache | 永久（append-only） | 同一 date 的旧数据被新数据覆盖 |
| realtime_cache | 30s | 市场时段每次 L0 轮询强制覆盖 |
| shares_cache | 永久（append-only） | 同一 date 的旧数据被新数据覆盖 |
| volume_cache | 永久（append-only） | 同一 date 的旧数据被新数据覆盖 |
| macro_cache | 永久（append-only） | 月度数据按月覆盖，宏观日频按日覆盖 |

### 2.5 已知问题（需在重构中解决）

#### Critical
1. **全局禁用 SSL 验证** — `ssl._create_default_https_context` 进程级别禁用，所有 HTTPS 跳过证书校验
2. **无认证/鉴权** — CORS 全开，任何人都能增删 ETF、清空数据库
3. **SQLite 多线程写入** — `check_same_thread=False` + 多线程 `INSERT`，存在损坏风险

#### High Priority
4. **单体文件** — `app.py` 3203行 + `index.html` 2470行，无模块拆分
5. **日期格式混乱** — `shares_cache` 用 `YYYYMMDD`，`volume_cache` 用 `YYYY-MM-DD`，`macro_cache` 混用
6. **全局可变状态无锁** — `_config`、`_etf_data_cache` 等被多线程修改，仅两把锁
7. **回填 O(n) 串行** — 从 2019 年逐日循环 ~1700 次 HTTP 请求
8. **交易日计算是伪实现** — `_get_trading_dates` 不区分节假日，直接往前数天数
9. **akshare 函数内重复 import** — 每次调用都 `import akshare`，初始化开销大
10. **无 akshare 版本锁定** — API 列名变化静默失败

#### Medium
11. **零测试** — 核心业务逻辑（评分算法、预警逻辑）无任何测试覆盖
12. **配置两套** — `config.json` 和 SQLite `cache_meta`/`index_cache` 重复存储
13. **硬编码魔法值** — 回填起始日期、预警阈值、市场时间窗口散布各处
14. **`_do_scheduled_refresh` 与 `do_l2` 代码重复**

---

## 三、重构架构设计

### 3.1 项目结构

```
super-money-printer/
├── backend/
│   ├── __init__.py
│   ├── main.py                 # FastAPI 入口，路由挂载
│   ├── config.py               # Pydantic Settings，统一配置管理
│   │
│   ├── models/                 # 数据模型
│   │   ├── __init__.py
│   │   ├── etf.py             # ETF 相关模型
│   │   ├── macro.py           # 宏观指标模型
│   │   ├── index.py           # 指数模型
│   │   └── stock.py            # 股票模型
│   │
│   ├── db/                     # 数据库层
│   │   ├── __init__.py
│   │   ├── connection.py       # 连接管理（支持 SQLite/PostgreSQL）
│   │   ├── schema.py           # 表结构定义
│   │   ├── migrations.py       # 数据库迁移
│   │   └── repositories/       # 数据访问对象
│   │       ├── __init__.py
│   │       ├── shares.py       # ETF 份额 Repository
│   │       ├── volume.py       # 成交量 Repository
│   │       ├── macro.py        # 宏观数据 Repository
│   │       ├── index.py        # 指数数据 Repository
│   │       └── stock.py        # 股票数据 Repository
│   │
│   ├── providers/              # ⭐ 多数据源抽象层（核心新增）
│   │   ├── __init__.py
│   │   ├── base.py             # BaseProvider 抽象基类
│   │   ├── registry.py         # ProviderRegistry 注册中心
│   │   ├── exceptions.py       # Provider 异常定义
│   │   ├── retry.py            # 重试策略
│   │   │
│   │   ├── baostock/          # ⭐ Baostock（K线主数据源）
│   │   │   ├── __init__.py
│   │   │   └── provider.py
│   │   ├── sse/               # 上交所（ETF份额主数据源）
│   │   │   ├── __init__.py
│   │   │   └── provider.py
│   │   ├── szse/              # 深交所（ETF份额快照，仅今日）
│   │   │   ├── __init__.py
│   │   │   └── provider.py
│   │   ├── akshare/           # AkShare（宏观指标+实时行情）
│   │   │   ├── __init__.py
│   │   │   ├── provider.py
│   │   │   └── field_mapping.py  # 列名字段映射
│   │   ├── tushare/           # Tushare（K线/份额 备选）
│   │   │   ├── __init__.py
│   │   │   └── provider.py
│   │   ├── eastmoney/         # 东方财富（备选）
│   │   │   ├── __init__.py
│   │   │   └── provider.py
│   │   └── tencent/           # 腾讯证券（指数K线 备选）
│   │   └── sector/            # 板块数据（行业/概念板块K线，待实现）
│   │       ├── __init__.py
│   │       └── provider.py
│   │
│   ├── services/               # 业务逻辑层
│   │   ├── __init__.py
│   │   ├── etf_service.py     # ETF 份额/成交量业务逻辑
│   │   ├── macro_service.py   # 宏观指标聚合逻辑
│   │   ├── index_service.py   # 指数 K线业务逻辑
│   │   ├── stock_service.py   # 个股业务逻辑
│   │   ├── alert_service.py   # 预警判定逻辑
│   │   └── scheduler_service.py    # 定时调度逻辑
│   │   # ⚠ thermometer_service.py / decision_service.py 暂时搁置（效果待验证）
│   │
│   ├── routes/                 # API 路由
│   │   ├── __init__.py
│   │   ├── etf.py             # /api/etf/*
│   │   ├── macro.py           # /api/macro/*
│   │   ├── index.py           # /api/index/*
│   │   ├── stock.py           # /api/stock/*
│   │   ├── cache.py           # /api/cache/*
│   │   └── health.py          # /api/health
│   │
│   └── scheduler/               # 定时任务
│       ├── __init__.py
│       ├── scheduler.py        # APScheduler 配置
│       ├── jobs/               # 定时任务定义
│       │   ├── __init__.py
│       │   ├── etf_refresh.py
│       │   ├── macro_refresh.py
│       │   └── index_refresh.py
│       └── state.py            # 任务状态持久化
│
├── frontend/
│   ├── index.html              # 主页面（保持现有 UI 不变）
│   ├── js/
│   │   ├── app.js             # 入口，主状态管理
│   │   ├── services/
│   │   │   ├── api.js         # API 调用封装
│   │   │   └── websocket.js    # WebSocket 客户端
│   │   ├── charts/
│   │   │   ├── shares.js      # 份额走势图
│   │   │   ├── daily.js       # 申赎柱状图
│   │   │   ├── volume.js      # 成交量图
│   │   │   ├── kline.js       # K线图
│   │   │   ├── macro.js       # 宏观迷你图
│   │   │   ├── thermometer.js  # 温度计
│   │   │   └── stock.js       # 个股图
│   │   ├── components/
│   │   │   ├── tabs.js        # Tab 切换
│   │   │   ├── alertPanel.js  # 告警面板
│   │   │   ├── etfTable.js    # ETF 数据表
│   │   │   ├── macroCards.js  # 宏观指标卡片
│   │   │   └── progress.js    # 进度弹窗
│   │   └── utils/
│   │       ├── format.js      # 格式化工具
│   │       ├── storage.js     # localStorage 封装
│   │       └── chartSync.js   # 图表联动
│   ├── css/
│   │   └── styles.css         # 样式（保持现有设计系统不变）
│   └── static/
│       ├── echarts.min.js
│       ├── tailwind.min.js
│       ├── fonts.css
│       └── fonts/
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # pytest 配置
│   ├── test_providers/         # 数据源测试
│   ├── test_services/          # 业务逻辑测试
│   └── test_api/              # API 集成测试
│
├── scripts/
│   ├── init_db.py             # 数据库初始化
│   └── backfill.py            # 独立回填脚本
│
├── config/
│   ├── default.yaml           # 默认配置
│   ├── providers.yaml         # 数据源配置（账号/密钥/优先级）
│   └── alerts.yaml            # 预警阈值配置
│
├── pyproject.toml             # 项目依赖管理
├── Dockerfile
├── docker-compose.yml
└── CLAUDE.md                  # Claude Code 上下文
```

---

## 四、数据源抽象层设计（核心）

### 4.1 核心接口

```python
# providers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional, List, Dict, Any
from enum import Enum

class ProviderStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"

class KLineFreq(Enum):
    """K线频率枚举（实测验证：baostock 支持 d/w/m）"""
    DAILY = "d"
    WEEKLY = "w"
    MONTHLY = "m"

@dataclass
class FetchResult:
    """标准化数据获取结果（标量指标用 value，K线用 fields）"""
    indicator: str          # 指标名称，如 "etf_shares", "mainflow", "bond_10y"
    date: date              # 数据日期
    value: Any = None       # 标量指标原始值
    source: str             # 数据源名称，如 "SSE", "AkShare", "Tushare", "Baostock"
    fetched_at: datetime = field(default_factory=datetime.now)
    raw_data: Optional[Dict] = None  # 原始响应（用于调试）
    confidence: float = 1.0  # 可信度 0.0-1.0

    # ⭐ K线专用字段（与标量指标二选一）
    symbol: Optional[str] = None  # 标的代码，如 "sh.510050"，"sz.002387"
    freq: Optional[KLineFreq] = None  # K线频率
    fields: Optional[Dict[str, Any]] = None  # K线完整字段 dict

@dataclass
class HealthReport:
    status: ProviderStatus
    latency_ms: float
    last_success: Optional[datetime]
    error_count: int
    message: str = ""

class BaseProvider(ABC):
    """数据源抽象基类"""

    name: str                          # 唯一标识，如 "sse", "baostock", "akshare"
    display_name: str                  # 显示名，如 "上海证券交易所", "Baostock"
    priority: int                      # 优先级，数字越小优先级越高
    supports_history: bool             # 是否支持历史查询
    supports_freq: List[KLineFreq] = field(default_factory=list)  # ⭐ 支持的K线频率
    rate_limit_per_minute: int = 30   # 每分钟请求限制

    # 标记支持的指标类型（子类的类属性）
    supported_indicators: set = field(default_factory=set)

    @abstractmethod
    async def fetch(
        self, indicator: str, date_from: date, date_to: date,
        freq: Optional[KLineFreq] = None, symbol: Optional[str] = None
    ) -> List[FetchResult]:
        """
        获取指定日期范围的数据。
        K线类指标通过 freq + symbol 参数指定。
        """
        pass

    @abstractmethod
    def health_check(self) -> HealthReport:
        """健康检查"""
        pass

    def supports(self, indicator: str) -> bool:
        """检查是否支持某指标"""
        return indicator in self.supported_indicators

    def supports_kline_freq(self, freq: KLineFreq) -> bool:
        """检查是否支持某频率的K线"""
        return freq in self.supports_freq
```

### 4.2 ProviderRegistry（注册中心）

```python
# providers/registry.py

class ProviderRegistry:
    """
    数据源注册中心——多数据源的核心组件。

    职责:
    1. 管理所有注册的 Provider
    2. 按指标类型选择优先级最高的可用 Provider
    3. Provider 故障时自动切换（failover）
    4. 多源数据聚合
    """

    def __init__(self):
        self._providers: Dict[str, List[BaseProvider]] = {}  # indicator -> [providers]

    def register(self, provider: BaseProvider):
        """注册 Provider 到对应指标"""
        for indicator in provider.supported_indicators:
            if indicator not in self._providers:
                self._providers[indicator] = []
            self._providers[indicator].append(provider)
            # 按 priority 排序
            self._providers[indicator].sort(key=lambda p: p.priority)

    def get_primary(self, indicator: str) -> Optional[BaseProvider]:
        """获取某指标优先级最高的可用 Provider"""
        providers = self._providers.get(indicator, [])
        for p in providers:
            health = p.health_check()
            if health.status in (ProviderStatus.HEALTHY, ProviderStatus.DEGRADED):
                return p
        return None

    def get_all(self, indicator: str) -> List[BaseProvider]:
        """获取某指标所有可用的 Provider（按优先级排序）"""
        providers = self._providers.get(indicator, [])
        return [p for p in providers
                if p.health_check().status != ProviderStatus.UNAVAILABLE]

    async def fetch_with_fallback(
        self, indicator: str, date_from: date, date_to: date,
        freq: Optional[KLineFreq] = None, symbol: Optional[str] = None
    ) -> List[FetchResult]:
        """
        带 fallback 的数据获取。
        依次尝试各 Provider，优先使用返回数据最多的那个。
        K线类指标传入 freq + symbol 参数。
        """
        results = {}
        for provider in self.get_all(indicator):
            try:
                fetched = await provider.fetch(indicator, date_from, date_to)
                for r in fetched:
                    key = (r.indicator, r.date)
                    # 保留优先级最高的数据
                    if key not in results or provider.priority < results[key].source_priority:
                        results[key] = FetchResultWithPriority(r, provider.priority)
            except ProviderError as e:
                logger.warning(f"Provider {provider.name} failed: {e}")
                continue

        return [v.result for v in results.values()]

    def get_status(self) -> Dict[str, Dict[str, Any]]:
        """获取所有 Provider 的状态概览"""
        status = {}
        for indicator, providers in self._providers.items():
            status[indicator] = {
                "primary": providers[0].name if providers else None,
                "available_count": sum(
                    1 for p in providers
                    if p.health_check().status != ProviderStatus.UNAVAILABLE
                ),
                "providers": {
                    p.name: p.health_check().status.value for p in providers
                }
            }
        return status
```

### 4.3 指标类型定义与实测数据字段

```python
# models/indicator.py

class Indicator(Enum):
    # ETF 相关
    ETF_SHARES = "etf_shares"           # ETF 份额
    ETF_VOLUME = "etf_volume"           # ETF 成交量
    ETF_NET_FLOW = "etf_net_flow"       # ETF 资金流向
    ETF_REALTIME = "etf_realtime"        # ⭐ ETF 实时行情（东方财富33字段）

    # 宏观指标
    MAINFLOW = "mainflow"               # 主力净流入
    BOND_10Y = "bond_10y"              # 10年国债收益率
    SHIBOR_ON = "shibor_on"            # SHIBOR隔夜
    USD_CNY = "usd_cny"                # 美元/人民币
    PMI_MANUFACTURING = "pmi_mfg"      # 制造业PMI
    M2 = "m2"                          # M2货币供应量
    CPI = "cpi"                        # CPI同比
    LPR_1Y = "lpr_1y"                 # LPR 1年期
    SHRZGM = "shrzgm"                  # 社融存量同比

    # K线（ETF/指数/股票通用，频率由 freq 参数指定）
    KLINE = "kline"                    # ⭐ 统一K线指标，freq 区分日/周/月

    # 个股
    STOCK_REALTIME = "stock_realtime"   # ⭐ 股票实时行情
    STOCK_FUND_FLOW = "stock_fund_flow" # 个股资金流向
    STOCK_NEWS = "stock_news"           # 个股新闻

    # 板块（待实现）
    SECTOR_INDUSTRY = "sector_industry"   # 行业板块K线（日/周/月）
    SECTOR_CONCEPT = "sector_concept"    # 概念板块K线（日/周/月）
```

#### 各数据源实测字段对照表

**baostock K线（日/周/月线）**

| 字段名 | 类型 | 说明 |
|--------|------|------|
| `date` | str | 日期 YYYY-MM-DD |
| `code` | str | 标的代码，如 `sh.510050`，`sz.002387` |
| `open/high/low/close` | float | 开/高/低/收盘价 |
| `volume` | float | 成交量（股） |
| `amount` | float | 成交额（元） |
| `turn` | float | ⭐ 换手率（%） |
| `isST` | str | 是否ST（1/0） |
| `adjustflag` | str | 复权类型（1=前复权 2=后复权 3=不复权） |

> 频率通过 `frequency='d'/'w'/'m'` 参数指定，`supports_freq: [DAILY, WEEKLY, MONTHLY]`。

**akshare 东方财富实时行情（`fund_etf_spot_em`）**

| 标准字段 | EM列名（中文） | 说明 |
|---------|--------------|------|
| `code` | 代码 | |
| `name` | 名称 | |
| `close` | 最新价 | |
| `iopv` | IOPV实时估值 | ⭐ ETF专属 |
| `discount` | 基金折价率 | ⭐ ETF专属 |
| `prev_close` | 昨收 | |
| `open` | 开盘价 | |
| `high` | 最高价 | |
| `low` | 最低价 | |
| `change` | 涨跌额 | |
| `pct_chg` | 涨跌幅 | |
| `volume` | 成交量 | |
| `amount` | 成交额 | |
| `amplitude` | 振幅 | |
| `turnover` | 换手率 | |
| `vol_ratio` | 量比 | |
| `buy1/sell1` | 买一/卖一 | |
| `outer_disk` | 外盘 | |
| `inner_disk` | 内盘 | |
| `main_net_inflow` | 主力净流入-净额 | |
| `main_net_pct` | 主力净流入-净占比 | |
| `super_large_net_inflow` | 超大单净流入-净额 | |
| `super_large_net_pct` | 超大单净流入-净占比 | |
| `large_net_inflow` | 大单净流入-净额 | |
| `large_net_pct` | 大单净流入-净占比 | |
| `medium_net_inflow` | 中单净流入-净额 | |
| `medium_net_pct` | 中单净流入-净占比 | |
| `small_net_inflow` | 小单净流入-净额 | |
| `small_net_pct` | 小单净流入-净占比 | |
| `shares` | 最新份额 | ETF专属 |
| `mkt_cap` | 流通市值/总市值 | |
| `update_time` | 更新时间 | |

**akshare 新浪 K线（`fund_etf_hist_sina`）**

| 字段名 | 说明 |
|--------|------|
| `date` | 日期 |
| `prevclose` | ⭐ 前收盘价（baostock 无此字段） |
| `open/high/low/close` | OHLC |
| `volume` | 成交量 |
| `amount` | 成交额 |

**SSE 官方份额 API（`query.sse.com.cn`）**

| 标准字段 | API原始字段 | 说明 |
|---------|-----------|------|
| `code` | `SEC_CODE` | 基金代码 |
| `name` | `SEC_NAME` | 基金简称 |
| `etf_type` | `ETF_TYPE` | 单市/跨市 |
| `date` | `STAT_DATE` | 统计日期（YYYY-MM-DD） |
| `shares` | `TOT_VOL` × 10000 | 基金份额（亿份→份） |

> SSE API 支持按日期查询历史份额（akshare 1.18.64 实测 2026-06-26 有 863 条），TOT_VOL 单位为亿份需×10000；不传 STAT_DATE 默认返回最新数据。SZSE 仅支持当日快照。

**SZSE 官方 ETF 份额 API（`fund.szse.cn`，akshare 1.18.64 内部使用）**

| 字段 | 说明 |
|------|------|
| `基金代码` | 纯数字，如 `159919` |
| `基金简称` | 如 `沪深300ETF` |
| `基金类别` | ETF |
| `投资类别` | 股票型/货币市场基金 等 |
| `上市日期` | YYYY-MM-DD |
| `当前规模(份)` | 份数（带逗号格式，需解析，如 `17,921,775`） |
| `净值` | NAV |

- URL: `https://fund.szse.cn/api/report/ShowReport`
- Params: `SHOWTYPE=xlsx`, `CATALOGID=1000_lf`, `TABKEY=tab1`
- akshare 1.18.64 `fund_etf_scale_szse()` 有 bug（`pd.read_excel` 不接受 bytes），需手动 `pd.read_excel(BytesIO(resp.content), engine="openpyxl")`
- 仅返回当日快照，无历史数据

**SSE 官方 ETF 份额 API（`query.sse.com.cn`，akshare 1.18.64 内部使用）**

- URL: `https://query.sse.com.cn/commonQuery.do`
- Params: `isPagination=true`, `pageHelp.pageSize=10000`, `sqlId=COMMON_SSE_ZQPZ_ETFZL_XXPL_ETFGM_SEARCH_L`, `STAT_DATE=YYYY-MM-DD`
- Headers: `Referer: https://www.sse.com.cn/`
- 响应: JSON `data_json["result"]`，字段: `SEC_CODE`, `SEC_NAME`, `ETF_TYPE`, `STAT_DATE`, `TOT_VOL`
- `TOT_VOL` 单位亿份，需×10000

**akshare SHIBOR（`macro_china_shibor_all`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `日期` | YYYY-MM-DD |
| `shibor_on` | `O/N-定价` | 隔夜 SHIBOR |
| `shibor_1w` | `1W-定价` | 1周 |
| `shibor_1m` | `1M-定价` | 1月 |

> akshare 1.18.64 实测 2312 行数据（2015-05-08 起），17 列（含各期限涨跌幅）。

**akshare PMI（`macro_china_pmi`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `月份` | "2026年05月份" 格式，需转换 |
| `pmi_mfg` | `制造业-指数` | 制造业 PMI |
| `pmi_non_mfg` | `非制造业-指数` | 非制造业 PMI |

**akshare M2（`macro_china_money_supply`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `月份` | "2026年05月份" 格式，需转换 |
| `m2_yoy` | `货币和准货币(M2)-同比增长` | M2 同比（%） |
| `m1_yoy` | `货币(M1)-同比增长` | M1 同比（%） |
| `m0_yoy` | `流通中的现金(M0)-同比增长` | M0 同比（%） |

**akshare CPI（`macro_china_cpi`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `月份` | "2026年05月份" 格式，需转换 |
| `cpi_yoy` | `全国-同比增长` | CPI 同比（%） |
| `cpi_mom` | `全国-环比增长` | CPI 环比（%） |

**akshare LPR（`macro_china_lpr`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `TRADE_DATE` | YYYY-MM-DD |
| `lpr_1y` | `LPR1Y` | 1年期 LPR（%） |
| `lpr_5y` | `LPR5Y` | 5年期 LPR（%） |

> akshare 1.18.64 实测 1573 行数据（1991-04-21 起），`LPR1Y` 从 2019-08-20 开始有数据。

**akshare 社融（`macro_china_new_financial_credit`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `月份` | "2026年05月份" 格式，需转换 |
| `shrzgm_yoy` | `当月-同比增长` | 社融当月同比（%） |
| `shrzgm_accum_yoy` | `累计-同比增长` | 社融累计同比（%） |
| `shrzgm_amount` | `当月` | 当月新增（亿元） |

> 注：`macro_china_shrzgm`（商务部 data.mofcom.gov.cn）SSL 不可用，使用 `macro_china_new_financial_credit` 替代。

**akshare 10年国债（`bond_zh_us_rate`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `日期` | YYYY-MM-DD |
| `bond_10y` | `中国国债收益率10年` | 中国10年国债收益率（%） |

**akshare 美元/人民币（`currency_boc_safe`）**

| 标准字段 | 原始列名 | 说明 |
|---------|---------|------|
| `date` | `日期` | YYYY-MM-DD |
| `usd_cny` | `美元` | 美元兑人民币（×100，即 870.0 = 8.70） |

> 注：`美元` 列为 100 美元兑人民币，即 870.0 表示 USD/CNY = 8.70。

### 4.4 重试策略

```python
# providers/retry.py

from tenacity import (
    retry, stop_after_attempt, wait_exponential,
    retry_if_exception_type
)

class ProviderError(Exception):
    """数据源异常基类"""
    def __init__(self, provider: str, message: str, original: Exception = None):
        self.provider = provider
        self.original = original
        super().__init__(message)

class RateLimitError(ProviderError):
    """速率限制"""
    pass

class DataNotAvailableError(ProviderError):
    """数据不可用（如非交易日）"""
    pass

# 标准重试装饰器
def with_retry(provider_name: str, max_attempts: int = 3):
    return retry(
        stop=stop_after_attempt(max_attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type((RateLimitError, ProviderError)),
        before_sleep=lambda retry_state: logger.warning(
            f"[{provider_name}] Retry {retry_state.attempt_number}/{max_attempts}"
        )
    )
```

### 4.5 统一字段映射

```python
# providers/akshare/field_mapping.py

# ⭐ 实测验证的字段映射表（akshare 版本间可能变化，需持续维护）
FIELD_MAPPINGS = {
    # K线统一映射（baostock / akshare 通用）
    "kline": {
        # baostock
        "date": "date",
        "code": "symbol",
        "open": "open",
        "high": "high",
        "low": "low",
        "close": "close",
        "volume": "volume",
        "amount": "amount",
        "turn": "turnover",
        "isST": "is_st",
        "adjustflag": "adjust_flag",
        # akshare 新浪
        "prevclose": "prev_close",
        # akshare EM 实时
        "最新价": "close",
        "成交量": "volume",
        "成交额": "amount",
        "换手率": "turnover",
        "IOPV实时估值": "iopv",
        "基金折价率": "discount",
        "振幅": "amplitude",
        "量比": "vol_ratio",
        "外盘": "outer_disk",
        "内盘": "inner_disk",
        "主力净流入-净额": "main_net_inflow",
        "主力净流入-净占比": "main_net_pct",
        "超大单净流入-净额": "super_large_net_inflow",
        "超大单净流入-净占比": "super_large_net_pct",
        "大单净流入-净额": "large_net_inflow",
        "大单净流入-净占比": "large_net_pct",
        "中单净流入-净额": "medium_net_inflow",
        "中单净流入-净占比": "medium_net_pct",
        "小单净流入-净额": "small_net_inflow",
        "小单净流入-净占比": "small_net_pct",
        "买一": "buy1",
        "卖一": "sell1",
        "最新份额": "shares",
        "流通市值": "float_mkt_cap",
        "总市值": "mkt_cap",
    },
    "etf_shares": {
        "基金代码": "code",
        "SEC_CODE": "code",
        "基金简称": "name",
        "SEC_NAME": "name",
        "ETF类型": "etf_type",
        "统计日期": "date",
        "基金份额": "shares",
        "TOT_VOL": "shares_raw",
    },
    "mainflow": {
        "日期": "date",
        "主力净流入-净额": "main_net_inflow",
        "主力净流入-净占比": "main_net_pct",
    },
    "shibor": {
        "日期": "date",
        "O/N-定价": "shibor_on",
        "1W-定价": "shibor_1w",
        "1M-定价": "shibor_1m",
    },
    # 宏观指标（akshare 实测字段映射）
    "bond_10y": {
        "日期": "date",
        "中国国债收益率10年": "bond_10y",
    },
    "pmi": {
        "月份": "date",        # "2026年05月份" → "2026-05"
        "制造业-指数": "pmi_mfg",
        "非制造业-指数": "pmi_non_mfg",
    },
    "m2": {
        "月份": "date",
        "货币和准货币(M2)-同比增长": "m2_yoy",
        "货币(M1)-同比增长": "m1_yoy",
        "流通中的现金(M0)-同比增长": "m0_yoy",
    },
    "cpi": {
        "月份": "date",
        "全国-同比增长": "cpi_yoy",
        "全国-环比增长": "cpi_mom",
    },
    "lpr": {
        "TRADE_DATE": "date",
        "LPR1Y": "lpr_1y",
        "LPR5Y": "lpr_5y",
    },
    "shrzgm": {
        "月份": "date",
        "当月-同比增长": "shrzgm_yoy",
        "累计-同比增长": "shrzgm_accum_yoy",
        "当月": "shrzgm_amount",
    },
    "usd_cny": {
        "日期": "date",
        "美元": "usd_cny_raw",   # 原始值 ×100，需 ÷100 转为真实汇率
    },
    # 板块数据（akshare 实测字段映射）
    "sector_industry": {
        # 申万 index_hist_sw
        "代码": "symbol",
        "日期": "date",
        "收盘": "close",
        "开盘": "open",
        "最高": "high",
        "最低": "low",
        "成交量": "volume",
        "成交额": "amount",
        # 同花顺/东财行业K线
        "日期": "date",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "收盘价": "close",
        "成交量": "volume",
        "成交额": "amount",
    },
    "sector_concept": {
        # 同花顺/东财概念K线
        "日期": "date",
        "开盘价": "open",
        "最高价": "high",
        "最低价": "low",
        "收盘价": "close",
        "成交量": "volume",
        "成交额": "amount",
    },
}

def map_fields(df: pd.DataFrame, indicator: str) -> pd.DataFrame:
    """将 akshare/各Provider 返回的 DataFrame 列名标准化"""
    if indicator not in FIELD_MAPPINGS:
        return df
    mapping = FIELD_MAPPINGS[indicator]
    # 只重命名存在的列，避免 KeyError
    rename_cols = {k: v for k, v in mapping.items() if k in df.columns}
    return df.rename(columns=rename_cols)
```

---

## 五、数据库设计

### 5.1 统一日期格式

所有日期字段统一使用 `YYYY-MM-DD` 格式，不再混用 `YYYYMMDD`。

### 5.2 表结构

```sql
-- ⭐ K线缓存（ETF/指数/股票 统一存储，freq 区分日/周/月线）
CREATE TABLE kline_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,         -- "sh.510050", "sz.002387" 等
    freq        TEXT NOT NULL,         -- "d" / "w" / "m"
    date        TEXT NOT NULL,          -- YYYY-MM-DD
    open        REAL NOT NULL,
    high        REAL NOT NULL,
    low         REAL NOT NULL,
    close       REAL NOT NULL,
    volume      REAL,
    amount      REAL,
    turnover    REAL,                   -- 换手率（%）
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    UNIQUE(symbol, freq, date, source)
);
CREATE INDEX idx_kline_symbol_freq ON kline_cache(symbol, freq);
CREATE INDEX idx_kline_date ON kline_cache(date);

-- ETF 份额缓存
CREATE TABLE shares_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    date        TEXT NOT NULL,          -- 统一 YYYY-MM-DD
    shares      REAL NOT NULL,          -- 份数（原始单位，SSE返回亿份需×10000）
    source      TEXT NOT NULL,          -- "SSE", "AkShare", "Tushare"
    fetched_at  TEXT NOT NULL,          -- ISO timestamp
    UNIQUE(code, date, source)
);
CREATE INDEX idx_shares_code ON shares_cache(code);
CREATE INDEX idx_shares_date ON shares_cache(date);
CREATE INDEX idx_shares_source ON shares_cache(source);

-- 成交量缓存
CREATE TABLE volume_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    code        TEXT NOT NULL,
    date        TEXT NOT NULL,          -- YYYY-MM-DD
    volume      REAL NOT NULL,
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    UNIQUE(code, date, source)
);
CREATE INDEX idx_volume_code ON volume_cache(code);
CREATE INDEX idx_volume_date ON volume_cache(date);

-- 宏观指标缓存
CREATE TABLE macro_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    indicator   TEXT NOT NULL,         -- "mainflow", "bond_10y", "pmi_mfg" ...
    date        TEXT NOT NULL,          -- YYYY-MM-DD（周频/月频指标也用此格式）
    value       REAL NOT NULL,
    source      TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    UNIQUE(indicator, date, source)
);
CREATE INDEX idx_macro_indicator ON macro_cache(indicator);
CREATE INDEX idx_macro_date ON macro_cache(date);

-- 实时行情快照缓存（东方财富33字段，用于 IOPV/资金流向等实时指标）
CREATE TABLE realtime_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    symbol_type TEXT NOT NULL,         -- "etf" / "stock"
    fetched_at  TEXT NOT NULL,          -- ISO timestamp
    data        TEXT NOT NULL,          -- JSON 字符串，存储全部33字段
    UNIQUE(symbol, symbol_type)
);
CREATE INDEX idx_realtime_symbol ON realtime_cache(symbol);

-- 缓存元数据（追踪最后更新时间）
CREATE TABLE cache_meta (
    code        TEXT NOT NULL,          -- 指标代码或 "global"
    key         TEXT NOT NULL,          -- "last_fetch", "last_success", "error_count"
    value       TEXT NOT NULL,
    updated_at  TEXT NOT NULL,
    PRIMARY KEY (code, key)
);

-- 任务执行记录（用于断点续传）
CREATE TABLE task_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id     TEXT NOT NULL,          -- "backfill_etf", "backfill_macro"
    date        TEXT NOT NULL,          -- 已完成的日期
    status      TEXT NOT NULL,          -- "success", "failed"
    completed_at TEXT NOT NULL,
    UNIQUE(task_id, date)
);

-- 数据源健康状态
CREATE TABLE provider_health (
    provider    TEXT NOT NULL PRIMARY KEY,
    status      TEXT NOT NULL,           -- "healthy", "degraded", "unavailable"
    last_check  TEXT NOT NULL,
    latency_ms  REAL,
    error_msg   TEXT
);

-- 预警记录表（Job 失败或指标异常时写入，供「告警中心」tab 查询）
CREATE TABLE alert_records (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_type  TEXT NOT NULL,          -- "job_failure" / "data_stale" / "provider_down" / "etf_threshold"
    severity    TEXT NOT NULL,           -- "info" / "warning" / "error"
    source      TEXT NOT NULL,           -- "l3_evening" / "SSE" / "etf.510050" ...
    message     TEXT NOT NULL,
    detail      TEXT,                    -- JSON 额外详情
    acknowledged INTEGER NOT NULL DEFAULT 0,  -- 是否已确认
    created_at  TEXT NOT NULL,
    UNIQUE(alert_type, source, created_at)  -- 同类型同来源同分钟去重
);
CREATE INDEX idx_alert_acknowledged ON alert_records(acknowledged);
CREATE INDEX idx_alert_created ON alert_records(created_at DESC);

-- ⭐ 可配置的刷新任务调度表
CREATE TABLE refresh_jobs (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL UNIQUE,  -- "l0_realtime", "l1_daily", "l2_monthly", "l3_evening"
    layer           TEXT NOT NULL,         -- "L0" / "L1" / "L2" / "L3"
    cron_expr        TEXT NOT NULL,         -- 标准5段cron表达式，如 "0 16 * * 1-5"
    enabled         INTEGER NOT NULL DEFAULT 1,  -- 1=启用，0=禁用
    retry_enabled   INTEGER NOT NULL DEFAULT 1,  -- 失败是否自动重试
    retry_cron_expr TEXT,                   -- 重试cron，如 "0 17 * * 1-5"（次日同时间）
    retry_max       INTEGER NOT NULL DEFAULT 1,  -- 最大重试次数
    description     TEXT,                    -- 任务描述
    created_at     TEXT NOT NULL,
    updated_at     TEXT NOT NULL
);
CREATE INDEX idx_refresh_jobs_enabled ON refresh_jobs(enabled);
```

### 5.3 多源聚合查询

```sql
-- 获取某 ETF 某日的主数据（优先级最高的数据源）
SELECT code, date, shares, source
FROM shares_cache
WHERE code = ? AND date = ?
ORDER BY
    CASE source
        WHEN 'SSE' THEN 1
        WHEN 'Tushare' THEN 2
        WHEN 'AkShare' THEN 3
        ELSE 9
    END
LIMIT 1;

-- 跨源数据比对（检测异常）
SELECT code, date,
       AVG(shares) as avg_shares,
       MAX(shares) - MIN(shares) as spread,
       COUNT(DISTINCT source) as source_count
FROM shares_cache
WHERE code = ? AND date BETWEEN ? AND ?
GROUP BY code, date
HAVING COUNT(DISTINCT source) > 1;
```

---

## 六、API 设计

### 6.1 端点总览

| 方法 | 路径 | 描述 |
|------|------|------|
| GET | `/api/health` | 健康检查（含 Provider 状态） |
| GET | `/api/providers/status` | 所有数据源状态概览 |
| GET | `/api/etf/data` | ETF 数据（份额/成交量/告警） |
| GET | `/api/etf/list` | ETF 列表 |
| POST | `/api/etf/add` | 添加 ETF |
| DELETE | `/api/etf/{code}` | 移除 ETF |
| GET | `/api/etf/search?code=` | 搜索 ETF |
| GET | `/api/macro/data` | 宏观数据 |
| GET | `/api/macro/thermometer` | ~~温度计评分~~（暂时搁置） |
| GET | `/api/macro/decision` | ~~择时评分~~（暂时搁置） |
| GET | `/api/index/data` | 指数数据 |
| POST | `/api/index/add` | 添加指数 |
| DELETE | `/api/index/remove` | 移除指数 |
| GET | `/api/stock/{code}/kline` | 个股K线 |
| GET | `/api/stock/{code}/fund_flow` | 个股资金流 |
| GET | `/api/stock/{code}/news` | 个股新闻 |
| GET | `/api/cache/ranges` | 缓存日期范围 |
| POST | `/api/cache/refresh` | 刷新最新数据（可指定指标/Job） |
| GET | `/api/scheduler/jobs` | 查看所有刷新计划 |
| POST | `/api/scheduler/jobs` | 新增/修改刷新计划 |
| PATCH | `/api/scheduler/jobs/{job_id}` | 启用/禁用/修改单个Job |
| POST | `/api/scheduler/jobs/{job_id}/run` | 手动触发立即执行指定Job |
| GET | `/api/scheduler/jobs/{job_id}/history` | 查看Job执行历史 |
| GET | `/api/scheduler/jobs/{job_id}/status` | 查看Job当前状态（上次运行/下次运行/今日重试次数） |
| GET | `/api/cache/status` | 各指标「最后刷新时间」和状态 |
| POST | `/api/cache/backfill` | 回填历史数据 |
| POST | `/api/cache/clear` | 清空缓存 |
| GET | `/ws/progress` | WebSocket 进度推送 |

### 6.2 Provider 状态 API

```
GET /api/providers/status

Response:
{
  "providers": {
    "etf_shares": {
      "primary": "sse",
      "available_count": 2,
      "providers": {
        "sse": "healthy",
        "akshare": "healthy"
      }
    },
    "mainflow": {
      "primary": "akshare",
      "available_count": 1,
      "providers": {
        "akshare": "healthy"
      }
    }
  }
}
```

---

## 七、调度系统设计

### 7.1 使用 APScheduler

```python
# scheduler/scheduler.py

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore

scheduler = AsyncIOScheduler(
    jobstores={"default": MemoryJobStore()},
    job_defaults={
        "coalesce": True,       # 合并错过的执行
        "max_instances": 1,      # 同一任务最多一个实例
        "misfire_grace_time": 300,  # 5分钟内允许执行
    }
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# L0: 实时层 — 市场时段每30秒轮询实时行情
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
scheduler.add_job(
    run_l0_realtime_poll,
    CronTrigger(second=0),          # 每分钟第0秒触发（实际由节流控制30s间隔）
    id="l0_realtime_poll",
    replace_existing=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# L1: 日终层 — 每日 16:05，收盘结算后
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
scheduler.add_job(
    run_l1_daily_settle,
    CronTrigger(hour=16, minute=5),
    id="l1_daily_settle",
    replace_existing=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# L2: 月初层 — 每月1日 09:30，PMI/M2/CPI/LPR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
scheduler.add_job(
    run_l2_monthly_macro,
    CronTrigger(day=1, hour=9, minute=30),
    id="l2_monthly_macro",
    replace_existing=True,
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# L3: 傍晚增量 — 每日 18:00，主力/国债/美元/SHIBOR/社融
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
scheduler.add_job(
    run_l3_evening_macro,
    CronTrigger(hour=18, minute=0),
    id="l3_evening_macro",
    replace_existing=True,
)
```

### 7.1.1 各 Job 职责

| Job ID | 触发时间 | 职责 |
|--------|---------|------|
| `l0_realtime_poll` | 每分钟第0秒（节流30s） | 实时行情快照写入 realtime_cache |
| `l1_daily_settle` | 每日 16:05 | K线封存 + ETF份额 + 成交量 |
| `l2_monthly_macro` | 每月1日 09:30 | PMI / M2 / CPI / LPR / 社融 |
| `l3_evening_macro` | 每日 18:00 | 主力净流入 / 国债 / SHIBOR / 美元 |

### 7.2 手动刷新与重试机制

#### 7.2.1 手动刷新

任何 Job 都支持手动触发，不受定时限制：

```
POST /api/scheduler/jobs/{job_id}/run
Body: { "force": true }   // force=true 跳过节流，立即执行

POST /api/cache/refresh
Body: {
  "indicators": ["etf_shares", "kline"],  // 可选，指定指标；空=全量
  "symbols": ["sh.510050"],               // 可选，指定标的；空=全部
  "layer": "L1"                           // 可选，指定刷新层
}
```

手动刷新流程：
1. API 接收请求，写入 `task_log`（task_id=`manual__{job_id}___{timestamp}__）
2. 后台线程立即执行，不影响定时 Job
3. 执行结果写入 `task_log`（status=`success` / `failed`）
4. 失败时写入 `provider_health.error_msg`
5. 通过 WebSocket `/ws/progress` 推送执行进度（消息格式见 §9.3.6）

#### 7.2.2 失败重试

每个 Job 可配置 `retry_enabled` + `retry_cron_expr`：

```
Job l2_monthly_macro 失败 → 触发 retry
  ↓
检查 retry_enabled=1 且 retry_count < retry_max
  ↓
在 retry_cron_expr 时间（如次日 09:30）自动重新执行
  ↓
重试成功 → 记录 success，重试计数清零
重试失败 → retry_count++，下次整点再试
```

失败重试流程：
1. Job 执行后检查 `fetch_result`
2. 若失败 → 查询 `refresh_jobs` 的 `retry_enabled` 和 `retry_max`
3. `retry_count < retry_max` → 注册一次性重试 Job（`remove_on_completion=True`）
4. 重试成功或达到 `retry_max` → 写入 `provider_health` 告警

#### 7.2.3 指标最后成功时间

通过 `cache_meta` 表追踪每个指标的最后成功时间：

```sql
-- 记录宏观指标最后成功时间
INSERT INTO cache_meta (code, key, value, updated_at)
VALUES ('macro_pmi_mfg', 'last_success', '2026-06-01T09:31:22', '2026-06-01T09:31:22')
ON CONFLICT(code, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;

-- 查询某指标是否超过TTL（需刷新）
SELECT value FROM cache_meta WHERE code='macro_pmi_mfg' AND key='last_success';
```

前端展示各指标的「最后刷新时间」和「刷新状态」（正常/过期/失败）。

---

### 7.4 可配置的刷新计划（数据管理页面）

> 所有刷新计划通过「数据管理」页面管理，不另设独立管理后台。

#### 7.4.1 刷新计划存储

Job 配置不再写死在代码里，全部存入 `refresh_jobs` 表，APScheduler 启动时从数据库加载：

```python
# scheduler/scheduler.py

def load_jobs_from_db():
    """从 refresh_jobs 表加载所有启用的 Job"""
    rows = conn.execute(
        "SELECT job_id, layer, cron_expr, enabled, retry_enabled, retry_cron_expr, retry_max "
        "FROM refresh_jobs WHERE enabled = 1"
    ).fetchall()
    for row in rows:
        trigger = CronTrigger.from_crontab(row["cron_expr"])
        scheduler.add_job(
            id=row["job_id"],
            func=get_job_func(row["job_id"]),
            trigger=trigger,
            replace_existing=True,
        )
        logger.info(f"Loaded job {row['job_id']} with cron: {row['cron_expr']}")
```

#### 7.4.2 默认刷新计划（数据库初始化数据）

```sql
INSERT INTO refresh_jobs (job_id, layer, cron_expr, enabled, retry_enabled, retry_cron_expr, retry_max, description, created_at, updated_at) VALUES
('l0_realtime',  'L0', '0 * * * *',           1, 0, NULL,               0, '实时行情轮询（每分钟第0秒，代码层节流30s）', NOW(), NOW()),
('l1_daily',     'L1', '5 16 * * 1-5',        1, 1, '5 17 * * 1-5',    1, '日终结算：K线封存+份额+成交量',               NOW(), NOW()),
('l2_monthly',   'L2', '30 9 1 * *',          1, 1, '30 10 2 * *',     2, '月初宏观：PMI/M2/CPI/LPR/社融',               NOW(), NOW()),
('l3_evening',   'L3', '0 18 * * 1-5',        1, 1, '0 19 * * 1-5',    1, '傍晚宏观：主力/国债/SHIBOR/美元',             NOW(), NOW());
```

#### 7.4.3 刷新计划 API

```
GET /api/scheduler/jobs
Response:
{
  "jobs": [
    {
      "job_id": "l1_daily",
      "layer": "L1",
      "cron_expr": "5 16 * * 1-5",
      "enabled": true,
      "retry_enabled": true,
      "retry_max": 1,
      "description": "日终结算：K线封存+份额+成交量",
      "last_run_at": "2026-06-29T16:05:00",
      "last_run_status": "success",
      "next_run_at": "2026-06-30T16:05:00",
      "retry_count_today": 0
    },
    ...
  ]
}

PATCH /api/scheduler/jobs/l2_monthly
Body: { "enabled": false }          -- 禁用该 Job
Body: { "cron_expr": "45 9 1 * *" } -- 修改 cron 表达式

POST /api/scheduler/jobs
Body: { "job_id": "l4_custom", "layer": "L3", "cron_expr": "0 */2 * * *", ... }  -- 新增自定义 Job

GET /api/cache/status
Response:
{
  "indicators": [
    { "indicator": "etf_shares", "last_success": "2026-06-29T16:05:00", "status": "success", "ttl_seconds": 72000 },
    { "indicator": "pmi_mfg",    "last_success": "2026-06-01T09:31:22", "status": "stale",   "ttl_seconds": 2764800 },
    { "indicator": "mainflow",    "last_success": null,                    "status": "never",   "ttl_seconds": 90000 },
  ]
}

说明：
- `ttl_seconds`：该指标的新鲜度阈值（秒），后端根据指标类型硬编码或从 `indicator_ttl` 表读取
- `status`：后端计算 `(now - last_success) > ttl_seconds ? "stale" : "success"`，last_success=null 时为 "never"
```

#### 7.4.4 失败告警

- Job 失败达到 `retry_max` 后 → 任务状态变为「失败」，同时写入 `alert_records`（`alert_type=job_failure`）
- 页面顶栏 `task-status-chip` 显示红色脉冲动画（点击弹出 progress modal）
- 前端各缓存区块显示指标状态（正常/过期/从未刷新）
- 告警中心 tab（`tab-alerts`）查询 `alert_records` 未确认的记录列表

### 7.5 断点续传

```python
# scheduler/state.py

class TaskState:
    """任务执行状态持久化"""

    def mark_done(self, task_id: str, date: str):
        """标记某日期已完成"""
        conn.execute(
            "INSERT OR IGNORE INTO task_log (task_id, date, status, completed_at) VALUES (?, ?, 'success', ?)",
            (task_id, date, datetime.now().isoformat())
        )
        conn.commit()

    def get_remaining(self, task_id: str, start: date, end: date) -> List[date]:
        """获取尚未完成的任务日期列表（断点续传）"""
        rows = conn.execute(
            "SELECT date FROM task_log WHERE task_id = ? AND status = 'success' AND date BETWEEN ? AND ?",
            (task_id, start.isoformat(), end.isoformat())
        ).fetchall()
        done = {row["date"] for row in rows}
        all_dates = get_trading_dates_range(start, end)
        return [d for d in all_dates if d.isoformat() not in done]
```

---

## 八、配置管理

### 8.1 配置层次

```
环境变量 (优先级最高)
    ↓
config/providers.yaml (数据源配置: API密钥/账号/端点)
    ↓
config/alerts.yaml (预警阈值)
    ↓
config/default.yaml (默认配置)
```

### 8.2 Pydantic Settings

```python
# config.py

from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # 数据库
    database_url: str = "sqlite:///./etf_data.db"

    # 服务器
    host: str = "0.0.0.0"
    port: int = 6000

    # 数据源依赖（实测验证版本）
    akshare_version: str = "latest"  # ⭐ 1.13.0 已不在 PyPI，用最新稳定版；列名映射通过 FIELD_MAPPINGS 兼容
    baostock_version: str = "0.9.2"  # ⭐ 主要 K线数据源，pip 可直接安装

    # Tushare (备选)
    tushare_token: str = ""

    # 调度
    market_open_hour: int = 8
    market_close_hour: int = 16
    refresh_interval_market: int = 600   # 秒
    refresh_interval_offhour: int = 3600  # 秒

    # 回填
    backfill_start_date: str = "2019-01-01"

    # SSL
    ssl_verify: bool = True  # 默认开启，禁用需要显式配置

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

### 8.3 Alert 配置

```yaml
# config/alerts.yaml
alerts:
  etf:
    single_day:
      threshold: 30  # 亿份
      level: red
    three_day_total:
      threshold: 20  # 亿份
      level: yellow
    volume_ratio:
      threshold: 2.0  # 量比
      level: yellow
```

---

## 九、前端保持不变的设计要点

### 9.1 UI 风格保留清单

- **色彩系统**: `#0f1117` 深空黑背景，`#1a1f35` 渐变卡片，`#475569` 轴标签
- **ECharts 配色**: 24色调色板（crc32 确定性分配）
- **图表 grid 规范**: `{ top: 15~20, right: 15~20, bottom: 40, left: 65 }`
- **Tooltip 样式**: `backgroundColor: #1e293b, borderColor: #334155`
- **组件圆角**: `rounded-2xl` 主卡片，`rounded-lg` 按钮/输入框
- **动画**: `animate-slide` (opacity+translateY 0.4s)，`pulse-alert` (opacity 2s)
- **图表联动**: 自定义 mousemove + `dispatchAction(showTip)` 按日期匹配
- **Tab 切换**: 6 个面板，CSS `hidden` 类控制显隐
- **状态持久化**: `localStorage` 保存 activeTab/days/agg

### 9.2 仅调整部分

- `config.json` 中的预警阈值改为从 `/api/config/alerts` 端点读取（前端无硬编码）
- WebSocket 消息格式新增 Job 执行消息格式（`job_start/progress/done/error`），保留旧格式兼容（详见 §9.3.6）

### 9.3 数据管理页面（settings tab）

#### 9.3.1 页面区块结构

settings tab 采用 Tab 子导航，将内容分为两个子面板：

```
settings tab (tab-settings)
│
├── 添加ETF（现有，Tab-bar 不影响此区块）
│
└── Tab-bar: [数据管理 | 刷新计划]  ← 新增 Tab 切换
    │
    ├── 数据管理 Tab（默认激活）
    │   ├── 数据缓存 card
    │   │   ├── task-status-chip  ← 扩展：支持 Job 失败红色脉冲
    │   │   ├── 刷新 / 回填历史 / 清空  （现有按钮不变）
    │   │   └── cache-table        ← 扩展：每行增加「最后刷新」「状态」列
    │   ├── 宏观数据缓存 card
    │   │   └── macro-cache-table ← 扩展：每行增加「最后刷新」「状态」列
    │   ├── 指数管理 card         ← 合并：缓存 table + 添加输入框，同一个 card
    │   │   ├── 刷新 / 回填历史 按钮
    │   │   └── index-cache-table + 添加输入框
    │   └── 追踪的ETF card        ← 现有，补录到 spec
    │       └── ETF 列表 + 添加按钮
    │
    └── 刷新计划 Tab
        ├── Job 列表 table（可编辑 cron / 启用禁用 / 手动触发）
        └── 执行历史（task_log 最近10条）
```

#### 9.3.2 术语说明：Job vs Task

| 概念 | 层级 | 说明 |
|------|------|------|
| **Job** | 调度层 | APScheduler 层面的定时任务（l0_realtime / l1_daily / l2_monthly / l3_evening），存储在 `refresh_jobs` 表 |
| **Task** | 前端层 | 前端发起的操作类型，对应 `_taskState.task`（`refresh` / `backfill` / `macro_refresh`） |

Job 与 Task 的映射关系：
- `l0_realtime` → 对应实时行情轮询（前端无手动触发入口，自动运行）
- `l1_daily` → 映射到 `refresh` task
- `l2_monthly` → 映射到 `macro_refresh` task
- `l3_evening` → 映射到 `macro_refresh` task
- 手动回填 → `backfill` task（前端独有，非 Job）

#### 9.3.3 任务状态 chip（扩展）

```
task-status-chip 状态定义：
  - idle（无任务运行）：隐藏 chip
  - 任务运行中（_taskState.running=true）：显示蓝色脉冲 + 任务标签
    · refresh → "刷新中: {detail}"
    · backfill → "回填中: {detail}"
    · macro_refresh → "宏观刷新中: {detail}"
  - Job 失败超过重试上限：显示红色脉冲 + "⚠ 刷新失败"
    · 点击 chip → 弹出 progress modal 显示失败原因
    · 红色状态持续显示，直到该 Job 下次成功才消失
  - 全部成功（action=done）：短暂绿色 → 隐藏
```

chip 点击行为：
- `_taskState.running=true` 时：点击弹出 progress modal（现有行为）
- `_taskState.running=false` 且 Job 失败时：点击弹出 progress modal，显示失败原因和错误详情

progress modal 关闭行为：
- 用户手动点「× 关闭」：modal 关闭，后台任务继续运行，不受影响
- 任务自动完成（action=done/error）：3秒后自动关闭（现有行为）

#### 9.3.4 缓存表扩展

各缓存 table（ETF数据 / 宏观数据 / 指数数据）末尾新增两列：

| 列 | 来源 |
|----|------|
| 最后刷新 | `GET /api/cache/status` → `last_success` |
| 状态 | `GET /api/cache/status` → `status`（见下方计算规则） |

**状态计算规则**（stale TTL 由后端计算，前端仅渲染）：

| 数据类型 | 指标 key | stale 阈值 | 说明 |
|---------|---------|-----------|------|
| K线（日线） | `kline_daily` | > 20 小时 | 次交易日 09:30 前不视为过期 |
| 实时行情 | `etf_realtime` | > 120 秒 | 市场时段实时 |
| ETF份额 | `etf_shares` | > 20 小时 | 每日 16:05 更新 |
| 主力净流入 | `mainflow` | > 25 小时 | 每日 18:00 更新 |
| 10年国债 | `bond_10y` | > 25 小时 | 每日 18:00 更新 |
| SHIBOR | `shibor_on` | > 25 小时 | 每日 18:00 更新 |
| PMI（月频） | `pmi_mfg` | > 32 天 | 每月1日更新 |
| M2 | `m2` | > 35 天 | 每月中更新 |
| CPI | `cpi` | > 35 天 | 每月中更新 |
| LPR | `lpr_1y` | > 35 天 | 每月更新 |

状态样式：
- `success` = 绿色标签
- `stale` = 黄色标签
- `never` = 灰色标签（从未刷新过）
- `failed` = 红色脉冲

stale TTL 在 `cache_meta` 表中通过 `ttl_seconds` 字段存储（或在后端配置表 `indicator_ttl` 中），各指标首次注册时写入默认值。

#### 9.3.5 刷新计划管理区块（新增）

**Tab 切换**：在 settings tab 顶部的 Tab-bar 新增「刷新计划」按钮，点击切换到刷新计划面板。

**Job 列表**：

| Job ID | 层 | 定时 (cron) | 状态 | 上次运行 | 下次运行 | 操作 |
|--------|---|------------|------|---------|---------|------|
| l1_daily | L1 | `5 16 * * 1-5` | 启用 | 2026-06-29 16:05 ✅ | 2026-06-30 16:05 | ⏵ 立即触发 / ✏ 修改 / ⏸ 禁用 |
| l2_monthly | L2 | `30 9 1 * *` | 启用 | 2026-06-01 09:30 ✅ | 2026-07-01 09:30 | ⏵ 立即触发 / ✏ 修改 / ⏸ 禁用 |
| l3_evening | L3 | `0 18 * * 1-5` | 失败⚠ | 2026-06-28 18:00 ❌ | — | ⏵ 重试 / ✏ 修改 / ⏸ 禁用 |

> 「失败⚠」行在 Job 失败超过重试上限后出现，直到下次成功自动恢复为「启用」。

**编辑抽屉**：点击行内「✏ 修改」→ 右侧滑入 drawer（宽 400px），内容：

```
┌─────────────────────────────────────┐
│  修改刷新计划                    ✕  │
├─────────────────────────────────────┤
│  Job ID: l3_evening               │
│  描述: 傍晚宏观：主力/国债/SHIBOR/美元 │
│                                     │
│  执行周期                          │
│  ┌──────────────────────────────┐  │
│  │ [分] [时] [日] [月] [星期]     │  │
│  │   0   18   *   *   1-5       │  │
│  │  ↳ 每周一至周五 18:00          │  │
│  └──────────────────────────────┘  │
│                                     │
│  启用该计划    [toggle ON]          │
│                                     │
│  失败重试                            │
│  ┌──────────────────────────────┐  │
│  │ 自动重试: [toggle ON]         │  │
│  │ 最大重试次数: [2]             │  │
│  │ 重试时间: [0 19 * * 1-5]     │  │
│  └──────────────────────────────┘  │
│                                     │
│  [取消]              [保存修改]     │
└─────────────────────────────────────┘
```

cron 编辑器采用 5 列下拉（时/分/日/月/星期），右侧实时预览自然语言解释（如"每周一至周五 18:00"），避免用户直接编辑 cron 字符串出错。

**执行历史**：Job 列表下方显示 `task_log` 最近 10 条：

| 时间 | Job ID | 任务 | 状态 | 耗时 |
|------|--------|------|------|------|
| 2026-06-29 16:05:00 | l1_daily | 日终结算 | ✅ 成功 | 3.2s |
| 2026-06-28 18:00:00 | l3_evening | 傍晚宏观 | ❌ 失败 | 0.8s |

#### 9.3.6 WebSocket 消息格式

前端 WebSocket 保持连接 `/ws/progress`，用于接收 Job 执行进度推送。

**新格式（Job 执行消息）**：

```javascript
// Job 开始执行
{ "type": "job_start",  "job_id": "l1_daily", "layer": "L1",
  "task": "refresh", "ts": 1751234567.123 }

// Job 进度更新
{ "type": "job_progress", "job_id": "l1_daily",
  "progress": 0.45,       // 0.0 ~ 1.0
  "detail": "正在写入份额数据 (sh.510050)...",
  "ts": 1751234567.456 }

// Job 执行完成
{ "type": "job_done", "job_id": "l1_daily",
  "status": "success", "duration_ms": 3240, "ts": 1751234567.789 }

// Job 执行失败
{ "type": "job_error", "job_id": "l3_evening",
  "status": "failed", "error": "SSE API 超时: 5次重试均失败",
  "retry_count": 2, "retry_max": 2,
  "ts": 1751234567.789 }

// Job 失败恢复（下次成功时）
{ "type": "job_done", "job_id": "l3_evening",
  "status": "success", "was_failing": true, "ts": 1751234567.789 }
```

**兼容旧格式（前端保留解析）**：

```javascript
// 兼容现有 app.py 推送的消息格式（_taskState.running=true 期间）
{ "action": "refresh", "detail": "...", "ts": 1751234567 }
{ "action": "backfill", "detail": "...", "ts": 1751234567 }
{ "action": "macro_refresh", "detail": "...", "ts": 1751234567 }
{ "action": "done", "detail": "刷新完成", "ts": 1751234567 }
{ "action": "error", "detail": "刷新失败: ...", "ts": 1751234567 }
```

前端 `_taskState` 映射规则：
- `action=refresh|backfill|macro_refresh` → `_taskState.running=true`，chip 显示蓝色脉冲
- `action=done` → `_taskState.running=false`，短暂绿色后隐藏
- `action=error` → `_taskState.running=false`，chip 显示红色脉冲（持久）
- 新格式 `job_error` → 同 `action=error` 行为
- 新格式 `job_done` + `was_failing=true` → 清除红色脉冲，恢复 idle

### Phase 0: 准备工作
- [ ] 建立新项目目录结构
- [ ] 创建 `pyproject.toml`，锁定 akshare 版本
- [ ] **实测 AkShare 宏观指标**（开发 AkShareProvider 前必须）：10年国债、SHIBOR、PMI、M2、CPI、LPR、美元/人民币 — 确认函数名、返回字段、数据格式，更新 §2.3.2 和 §4.3 ✅ 已完成
- [ ] **实测 SSE/SZSE 官方 API**（开发 SSEProvider/SZSEProvider 前必须）：确认 HTTP 请求 URL、sqlId 参数、请求头、响应格式，更新 §4.3 ✅ 已完成
- [ ] 编写 baseline 测试（当前功能测试）
- [ ] 数据库 schema 迁移脚本

### Phase 1: 后端模块化（最高优先）
- [ ] `config.py` — Pydantic Settings 统一配置
- [ ] `db/` — 数据库连接 + Repository 层
- [ ] `models/` — Pydantic 模型
- [ ] `providers/base.py` + `providers/registry.py` — 核心抽象
- [ ] AkShareProvider 实现（依赖 Phase 0 实测结果）
- [ ] SSE Provider 实现（依赖 Phase 0 实测 SSE API）
- [ ] SZSE Provider 实现（从 `fund.szse.cn`）
- [ ] `services/` — 业务逻辑层（从现有 `app.py` 迁移）
- [ ] `alert_service.py` — 预警判定逻辑，写入 `alert_records` 表
- [ ] `routes/` — API 路由
- [ ] `scheduler/` — APScheduler 定时任务
- [ ] 单元测试覆盖（预警逻辑、Provider 抽象）
# ⚠ thermometer/decision 评分暂时搁置，不纳入 Phase 1-4

### Phase 2: 数据层稳定性
- [ ] 交易日历修复（从数据源获取真实交易日）
- [ ] AkShareProvider 字段映射 + Schema 校验
- [ ] 多数据源 failover（接入一个备选 Provider，如 Tushare）
- [ ] SSL per-request 配置（替代全局禁用）
- [ ] 事务批量化（多个 INSERT 合并为单次 commit）
- [ ] SQLite WAL 模式
- [ ] 断点续传（task_log 表）

### Phase 3: 前端模块化
- [ ] 将 `index.html` 中的 JS 拆分为 `js/services/`、`js/charts/`、`js/components/`
- [ ] 预警阈值从 API 读取（新增 `/api/config/alerts` 端点）
- [ ] settings tab 扩展：Tab 子导航（数据管理/刷新计划）、task-status-chip 红色脉冲、缓存表状态列、Job 列表 drawer 编辑器、WebSocket 新消息格式解析（详见 §9.3）
- [ ] CSS 保持不变（仅可读性整理）

### Phase 4: 安全与部署
- [ ] 认证/鉴权层（JWT）
- [ ] CORS 收紧
- [ ] Docker / Docker Compose
- [ ] CI/CD（GitHub Actions）

---

## 十一、关键设计决策记录

| 决策 | 选择 | 备选 | 理由 |
|------|------|------|------|
| 多数据源接口 | Provider 抽象基类 | Adapter 模式 | 更简单，职责更清晰 |
| 任务队列 | APScheduler + 后台线程 | Celery/Dramatiq | 轻量，避免引入 Redis 依赖 |
| 数据库 | SQLite（WAL）+ 预留 PostgreSQL | PostgreSQL 直接用 | 当前数据量 SQLite 足够 |
| 前端框架 | 保持 Vanilla JS | React/Vue | 用户满意现有 UI，改动风险大 |
| 配置管理 | Pydantic Settings | ENV 文件 | 类型安全，支持嵌套配置 |
| akshare 版本 | latest + FIELD_MAPPINGS | 锁定 1.13.0 | 1.13.0 已不在 PyPI，改用最新版+字段映射表兼容 |
| K线数据源 | Baostock（主） + Sina/EM（备） | Tencent（主） | Baostock 支持日/周/月三频率，字段丰富（含换手率） |
| K线存储 | 统一 kline_cache 表（freq 区分） | 分开 index_cache / stock_cache | ETF/指数/股票统一管理，减少表数量 |
| ETF份额（上交所） | SSE 官方 API（主） | AkShare/Tushare（备） | 官方数据最准确，支持约20日历史 |
| ETF份额（深交所） | SZSE 官方（仅今日） | Tushare（备） | SZSE 无历史，Tushare 可补充 |
| 实时行情 | AkShare EM（主） | EMProvider（备） | EMProvider 与 AkShare 底层同源，二者等效 |

### 11.1 标的代码格式约定

各数据源标的代码格式不一致，Provider 内部负责转换，对外统一使用 **baostock 格式**：

| 数据源 | 格式 | 示例 |
|--------|------|------|
| baostock | `sh.510050` / `sz.002387` | 标准格式（对内统一） |
| akshare 新浪 | `sh510050` | 去掉点号 |
| 东方财富 | `510050`（股票同码） | 纯数字 |
| SSE 官方 API | `510050` | 纯数字 |
| SZSE 官方 | 纯数字 | |

> Provider 在内部完成格式转换。例如 `SSEProvider.get_shares('510050')` 内部拼装 `SEC_CODE=510050`；`BaostockProvider.fetch_kline('sh.510050', freq='d')` 直接使用 baostock 原生格式。
