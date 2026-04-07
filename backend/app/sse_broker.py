import asyncio
import json
from collections import defaultdict
from typing import AsyncIterator, DefaultDict, List
import uuid


class SSEBroker:
    def __init__(self) -> None:
        self._subscribers: DefaultDict[uuid.UUID, List[asyncio.Queue[str]]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def subscribe(self, workspace_id: uuid.UUID) -> asyncio.Queue[str]:
        q: asyncio.Queue[str] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers[workspace_id].append(q)
        return q

    async def unsubscribe(self, workspace_id: uuid.UUID, q: asyncio.Queue[str]) -> None:
        async with self._lock:
            subs = self._subscribers.get(workspace_id, [])
            if q in subs:
                subs.remove(q)
            if not subs:
                self._subscribers.pop(workspace_id, None)

    async def publish(self, workspace_id: uuid.UUID, event: dict) -> None:
        line = f"data: {json.dumps(event, default=str)}\n\n"
        async with self._lock:
            for q in list(self._subscribers.get(workspace_id, [])):
                try:
                    q.put_nowait(line)
                except asyncio.QueueFull:
                    pass


broker = SSEBroker()
