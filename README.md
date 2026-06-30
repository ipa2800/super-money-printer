# Super Money Printer

ETF 监控仪表盘的多数据源重构。完整设计规格见 [`docs/spec.md`](docs/spec.md)。

## 项目目标

将单体 ETF 监控系统（`app.py` ~3200 行 + `index.html` ~2500 行）重构为多数据源、模块化、高稳定性的数据基础设施。**前端 UI 风格保持不变**，重点解决数据获取稳定性和多源 failover 问题。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.13 / FastAPI / APScheduler / SQLite (WAL) |
| 数据源 | Baostock (K线主) · SSE/SZSE 官方 (ETF份额) · AkShare (宏观+实时) · Tushare (备选) |
| 前端 | React 18 + TypeScript + Vite + TailwindCSS + ECharts 5 |
| 测试 | pytest + pytest-asyncio |

## 快速开始

```bash
# 安装依赖（conda 环境 supermoneyprinter）
pip install -e ".[dev]"

# 初始化数据库
python scripts/init_db.py

# 启动后端（默认端口 6000）
uvicorn backend.main:app --reload --port 6000

# 启动前端开发服务器（端口 5173）
cd frontend && npm install && npm run dev
```

## 项目结构

```
backend/
  providers/    # BaseProvider + ProviderRegistry + 各数据源实现
  services/     # ETF / Macro / Index / Stock / Alert 业务逻辑
  routes/       # FastAPI 路由
  scheduler/    # APScheduler 任务（L0/L1/L2/L3）
  db/           # SQLite 连接 + Repository 层

frontend/src/
  components/   # KLineChart / ETFTable / MacroGrid / ...
  tabs/         # 6 个 Tab 页
  hooks/        # useECharts / useWebSocket
  utils/        # cron / echarts / format

tests/
docs/spec.md    # 完整技术规格
```

## 数据源架构

每个数据源实现 `BaseProvider` 接口，`ProviderRegistry` 按指标选优先级最高的可用 Provider，失败时自动 failover。

| 指标 | 主 | 备 |
|------|----|----|
| K线 (d/w/m) | Baostock | AkShare / Tushare |
| ETF 份额（上交所） | SSE 官方 | AkShare / Tushare |
| ETF 份额（深交所） | SZSE 官方 | Tushare |
| 宏观指标 | AkShare | 部分有备选 |
| 实时行情 | AkShare EM | EMProvider |

> **注意**：SZSE 无历史数据 API，仅返回当日快照。

## 刷新策略

| 层 | 时机 | 内容 |
|----|------|------|
| L0 | 市场时段 30s 轮询 | 实时行情 |
| L1 | 每日 16:05 | K线封存 + ETF份额 + 成交量 |
| L2 | 每月 1 日 09:30 | PMI / M2 / CPI / LPR / 社融 |
| L3 | 每日 18:00 | 主力净流入 / 国债 / SHIBOR / 美元 |

刷新计划存于 `refresh_jobs` 表，可通过 Settings tab 动态修改（cron / 启用 / 重试），无需重启。

## 开发

```bash
pytest                                # 跑全部测试
pytest tests/test_stock_service.py    # 单文件
```

## 相关文档

- [`docs/spec.md`](docs/spec.md) — 完整技术规格、API、数据库 schema、调度设计
- [`CLAUDE.md`](CLAUDE.md) — Claude Code 项目指引

## 当前进度

- [x] Slice 1–5：项目骨架 → Provider 抽象 → 后端服务 → 6-tab 前端 + 调度管理
- [ ] 认证 / Docker / CI/CD