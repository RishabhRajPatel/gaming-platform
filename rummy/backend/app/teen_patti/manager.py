"""In-memory registry of live Teen Patti hands, keyed by table id.

Mirrors `services/game_manager.py`'s skeleton exactly. For a single-process
deployment this is sufficient; horizontal scaling would need this behind Redis, same
caveat as the Deals Rummy manager.
"""
from __future__ import annotations

from threading import RLock
from typing import Dict, Optional

from app.teen_patti.engine import GameConfig, TeenPattiHand


class TeenPattiGameManager:
    def __init__(self) -> None:
        self._hands: Dict[str, TeenPattiHand] = {}
        self._lock = RLock()

    def get(self, table_id: str) -> Optional[TeenPattiHand]:
        with self._lock:
            return self._hands.get(table_id)

    def get_or_create(self, table_id: str, config: Optional[GameConfig] = None) -> TeenPattiHand:
        with self._lock:
            hand = self._hands.get(table_id)
            if hand is None:
                hand = TeenPattiHand(table_id, config)
                self._hands[table_id] = hand
            return hand

    def remove(self, table_id: str) -> None:
        with self._lock:
            self._hands.pop(table_id, None)

    def active_tables(self) -> list[str]:
        with self._lock:
            return list(self._hands.keys())


# process-wide singleton
teen_patti_manager = TeenPattiGameManager()
