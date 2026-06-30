"""WebSocket /ws/progress — 客户端订阅 scheduler 进度。"""
from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.scheduler.bus import encode, get_bus

log = logging.getLogger(__name__)

router = APIRouter(tags=["ws"])


@router.websocket("/ws/progress")
async def ws_progress(websocket: WebSocket):
    await websocket.accept()
    bus = get_bus()
    q = await bus.subscribe()
    log.info("[ws] client connected")
    try:
        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=30.0)
                await websocket.send_text(encode(msg))
            except asyncio.TimeoutError:
                # 心跳 — 防中间设备超时断连
                await websocket.send_text('{"type":"heartbeat"}')
    except WebSocketDisconnect:
        pass
    except Exception as e:
        log.warning(f"[ws] error: {e}")
    finally:
        await bus.unsubscribe(q)
        log.info("[ws] client disconnected")