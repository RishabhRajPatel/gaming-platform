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


class AndarBaharTable(UUIDMixin, TimestampMixin, Base):
    """A real-time Andar Bahar table's configuration + live status."""
    __tablename__ = "andar_bahar_tables"

    # Explicit Postgres enum type names — `teen_patti/models.py` defines its own
    # `TableMode`/`TableStatus` classes with the same name; SQLAlchemy would derive
    # the same default Postgres type name ("tablemode") for both, which collides
    # (DuplicateObject) the moment both migrations have run against the same
    # database. SQLite (tests/dev) has no native enum type so this only bites on
    # Postgres — naming it explicitly here avoids that landmine outright.
    name: Mapped[str] = mapped_column(String(80), default="Andar Bahar")
    mode: Mapped[TableMode] = mapped_column(
        SAEnum(TableMode, name="andar_bahar_table_mode"), default=TableMode.VIRTUAL
    )
    status: Mapped[TableStatus] = mapped_column(
        SAEnum(TableStatus, name="andar_bahar_table_status"), default=TableStatus.OPEN
    )
    max_players: Mapped[int] = mapped_column(Integer, default=8)
    betting_seconds: Mapped[int] = mapped_column(Integer, default=15)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    join_code: Mapped[Optional[str]] = mapped_column(String(8), unique=True, index=True, nullable=True)


class AndarBaharRound(UUIDMixin, TimestampMixin, Base):
    """History of every Andar Bahar bet/round for audit and provable-fairness replay.

    Used by both the one-shot REST endpoint (`table_id` null, as it always was) and
    the real-time WebSocket table (`table_id` set) — one shared audit trail.
    """
    __tablename__ = "andar_bahar_rounds"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    table_id: Mapped[Optional[str]] = mapped_column(String(36), nullable=True, index=True)
    mode: Mapped[str] = mapped_column(String(10), default="virtual")  # virtual | real
    bet: Mapped[str] = mapped_column(String(6))                       # andar | bahar
    stake: Mapped[int] = mapped_column(BigInteger)
    winner: Mapped[str] = mapped_column(String(6))
    payout: Mapped[int] = mapped_column(BigInteger, default=0)
    won: Mapped[bool] = mapped_column(Boolean, default=False)
    cards_dealt: Mapped[int] = mapped_column(Integer, default=0)

    client_seed: Mapped[str] = mapped_column(String(120), default="")
    nonce: Mapped[int] = mapped_column(BigInteger, default=0)
    server_seed: Mapped[str] = mapped_column(String(64), default="")
    server_seed_hash: Mapped[str] = mapped_column(String(64), default="")
