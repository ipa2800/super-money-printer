# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

`super-money-printer` is a refactor of the existing ETF monitoring dashboard located at:
`/Users/peggy/.openclaw/workspace-padiya/scripts/etf_dashboard/`

The refactor's core goal is to improve **data acquisition stability and multi-source architecture** while preserving the existing UI/UX. The reference codebase (`app.py` ~3200 lines, `templates/index.html` ~2500 lines) should be read in full before making architectural decisions.

## Source of Truth

All architectural decisions, data source design, and refactoring phases are documented in `docs/spec.md`. Read it before writing any code. Key design decisions include:

- **Provider abstraction** (`providers/base.py` → `providers/registry.py`): each data source (SSE, SZSE, AkShare, Tushare, EastMoney, Tencent) implements `BaseProvider`
- **Date format**: all dates stored as `YYYY-MM-DD` — the reference codebase mixes `YYYYMMDD` and `YYYY-MM-DD`, which is a known bug to fix
- **akshare version pinning**: locked to `akshare==1.13.0` — column name changes across versions are a known failure mode
- **SSL**: per-request `verify=False` only, not global `ssl._create_default_https_context` override
- **No authentication** in reference codebase — auth layer to be added in Phase 4

## Architecture

```
backend/
  providers/     # Data source abstraction (BaseProvider, ProviderRegistry)
  services/      # Business logic (ETF, Macro, Index, Stock, Alert, Thermometer, Decision)
  routes/        # FastAPI endpoints
  scheduler/     # APScheduler jobs (L1/L2/L3 refresh layers)
  db/            # SQLite connection + repositories

frontend/
  index.html     # Single-page app — UI style MUST be preserved exactly
  js/            # Services, charts, components (modularized from current single <script> block)

tests/
  test_providers/
  test_services/
```

## Data Source Types

| Indicator | Primary Source | Backup Sources |
|-----------|--------------|---------------|
| ETF shares (SSE) | query.sse.com.cn HTTP | AkShare, Tushare |
| ETF shares (SZSE) | fund.szse.cn XLSX (snapshot only!) | Tushare |
| ETF volume | AkShare `fund_etf_hist_sina()` | Tushare |
| Macro indicators | AkShare various modules | Tushare |
| Index K-line | Tencent web.ifzq.gtimg.cn | AkShare |
| Stock data | AkShare modules | Tushare |

**Note**: SZSE has no historical data API — this must be clearly documented in UI and provider code.

## UI Constraints

The frontend UI must remain visually identical to the reference. Specifically:
- Dark theme: background `#0f1117`, cards `linear-gradient(135deg, #1a1f35, #141829)`
- ECharts 5 with 24-color deterministic palette (crc32 assignment)
- Chart grid: `{ top: 15-20, right: 15-20, bottom: 40, left: 65 }`
- Tooltip style: `backgroundColor: #1e293b, borderColor: #334155`
- Tab panels controlled by CSS `hidden` class
- All chart code in `templates/index.html` at reference path — copy rendering logic exactly when modularizing

## Working with the Reference Codebase

Before modifying any backend logic, read the corresponding section in `app.py` at the reference path:
- Data fetching: lines 530-1136 (share/volume/macro fetchers)
- Scheduling: lines 119-354 (refresh loop, L1/L2/L3 layers)
- Alert logic: search `alert` in `app.py`
- Thermometer/decision scoring: search `thermometer` / `decision` in `app.py`

The reference codebase has these known issues — do not replicate them:
1. SSL verification globally disabled (line 35: `ssl._create_default_https_context = ...`)
2. `check_same_thread=False` on SQLite connections in multi-threaded writes
3. `_get_trading_dates()` approximates trading days (counts calendar days, not actual trading days)
4. akshare imported inside functions rather than at module level
5. Date format inconsistency across cache tables

## Commands

No `pyproject.toml` or build tooling exists yet (Phase 0 not started). Once established:

```bash
# Install dependencies
uv sync

# Run tests
pytest

# Run a single test file
pytest tests/test_providers/test_registry.py -v

# Start development server
uvicorn backend.main:app --reload --port 6000

# Database initialization
python scripts/init_db.py
```

## Key Files to Read First

- `docs/spec.md` — full architectural specification
- Reference: `app.py` lines 530-1136 — all data fetching logic
- Reference: `app.py` lines 119-354 — scheduling and refresh
- Reference: `templates/index.html` — full UI implementation
