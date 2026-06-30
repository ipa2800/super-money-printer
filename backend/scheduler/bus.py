"""Job progress pubsub — WebSocket clients subscribe, scheduler jobs broadcast。"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

log = logging.getLogger(__name__)


class ProgressBus:
    """进程级消息总线: 任意 task 可以 broadcast(dict), 所有订阅者收到。"""

    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue] = set()
        self._lock = asyncio.Lock()

    async def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.add(q)
        log.info(f"[bus] subscribe (total={len(self._subscribers)})")
        return q

    async def unsubscribe(self, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers.discard(q)
        log.info(f"[bus] unsubscribe (total={len(self._subscribers)})")

    async def broadcast(self, message: dict[str, Any]) -> None:
        """异步广播 — 满了就丢, 不阻塞 scheduler。"""
        async with self._lock:
            dead = []
            for q in self._subscribers:
                try:
                    q.put_nowait(message)
                except asyncio.QueueFull:
                    log.warning("[bus] subscriber queue full, dropping")
                    dead.append(q)
            for q in dead:
                self._subscribers.discard(q)

    def broadcast_nowait(self, message: dict[str, Any]) -> None:
        """同步 broadcast — 给非 async 上下文用 (目前 jobs 都是 async, 但留接口)。"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                loop.create_task(self.broadcast(message))
            else:
                loop.run_until_complete(self.broadcast(message))
        except RuntimeError:
            pass


# 全局单例
_bus: ProgressBus | None = None


def get_bus() -> ProgressBus:
    global _bus
    if _bus is None:
        _bus = ProgressBus()
    return _bus


def reset_bus() -> None:
    global _bus
    _bus = None


def encode(msg: dict[str, Any]) -> str:
    return json.dumps(msg, ensure_ascii=False, default=str)