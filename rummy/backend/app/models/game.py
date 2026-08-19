from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class TableMode(str, Enum):
    REAL_MONEY = "real_money"
    FREE = "free"


class TableStatus(str, Enum):
    OPEN = "open"
    RUNNING = "running"
    FINISHED = "finished"


class GameTable(UUIDMixin, TimestampMixin, Base):
    """A Deals Rummy table configuration + live status."""
    __tablename__ = "game_tables"

    name: Mapped[str] = mapped_column(String(80), default="Deals Rummy")
    mode: Mapped[TableMode] = mapped_column(SAEnum(TableMode), default=TableMode.FREE)
    status: Mapped[TableStatus] = mapped_column(SAEnum(TableStatus), default=TableStatus.OPEN)
    max_players: Mapped[int] = mapped_column(Integer, default=4)
    num_deals: Mapped[int] = mapped_column(Integer, default=2)
    entry_fee_paise: Mapped[int] = mapped_column(BigInteger, default=0)   # 0 for free tables
    pool_limit: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # e.g. 101/201; Pool Rummy when set
    turn_seconds: Mapped[int] = mapped_column(Integer, default=30)
    starting_chips: Mapped[int] = mapped_column(Integer, default=160)
    is_private: Mapped[bool] = mapped_column(Boolean, default=False)
    join_code: Mapped[Optional[str]] = mapped_column(String(8), unique=True, index=True, nullable=True)

    rounds = relationship("GameRound", back_populates="table", cascade="all, delete-orphan")


class GameRound(UUIDMixin, TimestampMixin, Base):
    """A finished game (all deals) result, for history/audit and replay."""
    __tablename__ = "game_rounds"

    table_id: Mapped[str] = mapped_column(ForeignKey("game_tables.id"), index=True)
    winner_user_id: Mapped[str] = mapped_column(String(36), nullable=True)
    deals_played: Mapped[int] = mapped_column(Integer, default=0)
    # JSON-serialisable per-player result + the RNG seeds, stored as text for portability
    result_json: Mapped[str] = mapped_column(String, default="{}")
    prize_pool_paise: Mapped[int] = mapped_column(BigInteger, default=0)

    table = relationship("GameTable", back_populates="rounds")
