from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class TableMode(str, Enum):
    VIRTUAL = "virtual"
    REAL = "real"


class TableStatus(str, Enum):
    OPEN = "open"
    RUNNING = "running"
    FINISHED = "finished"


class TeenPattiTable(UUIDMixin, TimestampMixin, Base):
    """A Teen Patti WebSocket table's configuration + live status."""
    __tablename__ = "teen_patti_tables"

    # Explicit Postgres enum type names — `models/game.py` (Deals Rummy) already
    # defines its own `TableMode`/`TableStatus` classes with the same class name;
    # SQLAlchemy would otherwise derive the same default Postgres type name
    # ("tablemode") for both, colliding (DuplicateObject) the moment both
    # migrations run against the same database. SQLite (tests/dev) has no native
    # enum type so this only bites on Postgres.
    name: Mapped[str] = mapped_column(String(80), default="Teen Patti")
    mode: Mapped[TableMode] = mapped_column(
        SAEnum(TableMode, name="teen_patti_table_mode"), default=TableMode.VIRTUAL
    )
    status: Mapped[TableStatus] = mapped_column(
        SAEnum(TableStatus, name="teen_patti_table_status"), default=TableStatus.OPEN
    )
    max_players: Mapped[int] = mapped_column(Integer, default=4)
    boot_amount: Mapped[int] = mapped_column(BigInteger, default=10)
    turn_seconds: Mapped[int] = mapped_column(Integer, default=15)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    join_code: Mapped[Optional[str]] = mapped_column(String(8), unique=True, index=True, nullable=True)


class TeenPattiHandHistory(UUIDMixin, TimestampMixin, Base):
    """History of every Teen Patti hand for audit and provable-fairness replay.

    Used by both the one-shot REST endpoint (`table_id` null) and the real-time
    WebSocket table (`table_id` set) — one shared audit trail for the game.
    """
    __tablename__ = "teen_patti_hand_history"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    table_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(10), default="virtual")  # virtual | real
    boot: Mapped[int] = mapped_column(BigInteger)
    pot: Mapped[int] = mapped_column(BigInteger, default=0)
    winner_seat: Mapped[int] = mapped_column(Integer, default=0)
    won: Mapped[bool] = mapped_column(Boolean, default=False)
    payout: Mapped[int] = mapped_column(BigInteger, default=0)
    hand_json: Mapped[str] = mapped_column(String, default="{}")  # full TeenPattiHand.as_dict()

    client_seed: Mapped[str] = mapped_column(String(120), default="")
    nonce: Mapped[int] = mapped_column(BigInteger, default=0)
    server_seed: Mapped[str] = mapped_column(String(64), default="")
    server_seed_hash: Mapped[str] = mapped_column(String(64), default="")
