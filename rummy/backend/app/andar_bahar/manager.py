"""In-memory registry of live Andar Bahar tables, keyed by table id.

Identical skeleton to `teen_patti/manager.py` / `services/game_manager.py`.
"""
from __future__ import annotations

from threading import RLock
from typing import Dict, Optional

from .table import AndarBaharTable, TableConfig


class AndarBaharTableManager:
    def __init__(self) -> None:
        self._tables: Dict[str, AndarBaharTable] = {}
        self._lock = RLock()

    def get(self, table_id: str) -> Optional[AndarBaharTable]:
        with self._lock:
            return self._tables.get(table_id)

    def get_or_create(self, table_id: str, config: Optional[TableConfig] = None) -> AndarBaharTable:
        with self._lock:
            table = self._tables.get(table_id)
            if table is None:
                table = AndarBaharTable(table_id, config)
                self._tables[table_id] = table
            return table

    def remove(self, table_id: str) -> None:
        with self._lock:
            self._tables.pop(table_id, None)

    def active_tables(self) -> list[str]:
        with self._lock:
            return list(self._tables.keys())


# process-wide singleton
andar_bahar_manager = AndarBaharTableManager()
