"""In-memory registry of live Deals Rummy games, keyed by table id.

For a single-process deployment this is sufficient. For horizontal scaling, the
authoritative game state should move behind Redis (one owner process per table) and this
manager becomes the local cache for the table's owning worker. The engine itself is
already serialisable via `public_state()` + per-player hands.
"""
from __future__ import annotations

from threading import RLock
from typing import Dict, Optional

from app.game_engine.deals_rummy import DealsRummyGame, GameConfig


class GameManager:
    def __init__(self) -> None:
        self._games: Dict[str, DealsRummyGame] = {}
        self._lock = RLock()

    def get(self, table_id: str) -> Optional[DealsRummyGame]:
        with self._lock:
            return self._games.get(table_id)

    def get_or_create(self, table_id: str, config: GameConfig) -> DealsRummyGame:
        with self._lock:
            game = self._games.get(table_id)
            if game is None:
                game = DealsRummyGame(table_id, config)
                self._games[table_id] = game
            return game

    def remove(self, table_id: str) -> None:
        with self._lock:
            self._games.pop(table_id, None)

    def active_tables(self) -> list[str]:
        with self._lock:
            return list(self._games.keys())


# process-wide singleton
game_manager = GameManager()
