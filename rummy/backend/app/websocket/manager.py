"""WebSocket connection manager: tracks sockets per table and fans out messages.

One entry per (table_id, user_id). Reconnects replace the previous socket for that
user, which supports the "drop off the train, hop back on" reconnection flow.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._tables: Dict[str, Dict[str, WebSocket]] = defaultdict(dict)
        self._lock = asyncio.Lock()

    async def connect(self, table_id: str, user_id: str, ws: WebSocket) -> None:
        await ws.accept()
        async with self._lock:
            # replace any stale socket for this user
            old = self._tables[table_id].get(user_id)
            if old is not None:
                try:
                    await old.close()
                except Exception:
                    pass
            self._tables[table_id][user_id] = ws

    async def disconnect(self, table_id: str, user_id: str) -> None:
        async with self._lock:
            conns = self._tables.get(table_id)
            if conns and conns.get(user_id):
                conns.pop(user_id, None)
                if not conns:
                    self._tables.pop(table_id, None)

    async def send_to_user(self, table_id: str, user_id: str, message: dict) -> None:
        ws = self._tables.get(table_id, {}).get(user_id)
        if ws is not None:
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(table_id, user_id)

    async def broadcast(self, table_id: str, message: dict) -> None:
        for user_id, ws in list(self._tables.get(table_id, {}).items()):
            try:
                await ws.send_json(message)
            except Exception:
                await self.disconnect(table_id, user_id)

    def connected_users(self, table_id: str) -> list[str]:
        return list(self._tables.get(table_id, {}).keys())


manager = ConnectionManager()
