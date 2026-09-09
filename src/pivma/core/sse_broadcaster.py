import asyncio
import json
from collections.abc import AsyncGenerator
from typing import Any


class EventBroadcaster:
    """Gerenciador pub/sub em memória para Server-Sent Events (SSE)."""

    def __init__(self):
        self._operational_subscribers: set[asyncio.Queue] = set()
        self._ai_subscribers: set[asyncio.Queue] = set()

    def broadcast_operational(self, event_data: dict[str, Any]) -> None:
        """Envia evento para clientes do índice operacional."""
        for q in list(self._operational_subscribers):
            try:
                q.put_nowait(event_data)
            except asyncio.QueueFull:
                pass

    def broadcast_ai_step(self, step_data: dict[str, Any]) -> None:
        """Envia evento de etapa para clientes do canal de IA."""
        for q in list(self._ai_subscribers):
            try:
                q.put_nowait(step_data)
            except asyncio.QueueFull:
                pass

    async def subscribe_operational(self) -> AsyncGenerator[str, None]:
        """Gera eventos SSE para o canal operacional."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._operational_subscribers.add(q)
        try:
            yield ': connected\n\n'
            while True:
                try:
                    event = await asyncio.wait_for(q.get(), timeout=15.0)
                    payload = json.dumps(event, default=str)
                    yield f'data: {payload}\n\n'
                except asyncio.TimeoutError:
                    yield ': keepalive\n\n'
        finally:
            self._operational_subscribers.discard(q)

    async def subscribe_ai(self) -> AsyncGenerator[str, None]:
        """Gera eventos SSE para o canal de IA."""
        q: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._ai_subscribers.add(q)
        try:
            yield ': connected\n\n'
            while True:
                try:
                    step = await asyncio.wait_for(q.get(), timeout=15.0)
                    payload = json.dumps(step, default=str)
                    yield f'data: {payload}\n\n'
                except asyncio.TimeoutError:
                    yield ': keepalive\n\n'
        finally:
            self._ai_subscribers.discard(q)


broadcaster = EventBroadcaster()
