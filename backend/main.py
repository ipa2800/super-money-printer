"""FastAPI app — lifespan 启动/关停 ProviderRegistry。"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.providers.akshare import AkShareProvider
from backend.providers.baostock import BaostockProvider
from backend.providers.registry import get_registry
from backend.providers.sse import SSEProvider
from backend.providers.szse import SZSEProvider
from backend.providers.tushare import TushareProvider
from backend.routes import alerts, cache, etf, health, index, jobs, macro, stocks, ws
from backend.scheduler import get_scheduler

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("super-money-printer")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("=" * 50)
    log.info("super-money-printer 启动中...")

    # 初始化 DB schema (含 pool 表)
    from backend.db.connection import get_connection
    from backend.db.schema import init_schema
    init_schema(get_connection())

    # 注册所有 providers
    registry = get_registry()
    registry.register(BaostockProvider())
    registry.register(AkShareProvider())
    registry.register(SSEProvider())
    registry.register(SZSEProvider())
    # Tushare 可选 — 没 token 跳过
    import os as _os
    if _os.environ.get("TUSHARE_TOKEN", "").strip():
        registry.register(TushareProvider())
    else:
        log.info("tushare skipped (TUSHARE_TOKEN not set)")
    await registry.bootstrap()

    # 启动 scheduler
    scheduler = get_scheduler()
    scheduler.start()

    log.info("✅ Provider registry + scheduler ready")
    log.info("=" * 50)
    yield
    log.info("关停中...")
    await scheduler.shutdown()
    await registry.shutdown()
    log.info("bye")


app = FastAPI(title="super-money-printer", version="0.1.0", lifespan=lifespan)

# CORS 全开 — Phase 4 收紧
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 静态资源 (echarts.min.js + app.js)
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
JS_DIR = FRONTEND_DIR / "js"
if JS_DIR.exists():
    app.mount("/js", StaticFiles(directory=str(JS_DIR)), name="js")

# 路由
app.include_router(health.router)
app.include_router(index.router)
app.include_router(macro.router)
app.include_router(etf.router)
app.include_router(jobs.router)
app.include_router(ws.router)
app.include_router(alerts.router)
app.include_router(cache.router)
app.include_router(stocks.router)


@app.get("/api/config/alerts")
async def config_alerts() -> dict:
    """前端从此端点读取预警阈值, 无硬编码。"""
    from backend.services.alert_service import AlertService
    return AlertService.get_config()


@app.get("/", include_in_schema=False)
async def root() -> FileResponse:
    """返回前端 index.html。"""
    return FileResponse(str(FRONTEND_DIR / "index.html"))