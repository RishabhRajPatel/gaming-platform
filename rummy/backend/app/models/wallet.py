from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class TxnType(str, Enum):
    DEPOSIT = "deposit"
    WITHDRAWAL = "withdrawal"
    GAME_STAKE = "game_stake"       # money moved into a table
    GAME_PAYOUT = "game_payout"     # winnings credited
    BONUS = "bonus"
    ADJUSTMENT = "adjustment"


class WalletKind(str, Enum):
    REAL = "real"          # withdrawable real money (paise)
    BONUS = "bonus"        # promotional, non-withdrawable
    VIRTUAL = "virtual"    # free-to-play chips


class Wallet(UUIDMixin, TimestampMixin, Base):
    """Balances are stored as **integer paise** (real/bonus) or integer chips (virtual).

    Never use floats for money.
    """
    __tablename__ = "wallets"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), unique=True, index=True)
    real_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    bonus_paise: Mapped[int] = mapped_column(BigInteger, default=0)
    virtual_chips: Mapped[int] = mapped_column(BigInteger, default=0)

    user = relationship("User", back_populates="wallet")
    transactions = relationship(
        "WalletTransaction", back_populates="wallet", cascade="all, delete-orphan"
    )


class WalletTransaction(UUIDMixin, TimestampMixin, Base):
    """Append-only ledger entry. `idempotency_key` prevents double-processing."""
    __tablename__ = "wallet_transactions"

    wallet_id: Mapped[str] = mapped_column(ForeignKey("wallets.id"), index=True)
    txn_type: Mapped[TxnType] = mapped_column(SAEnum(TxnType), nullable=False)
    kind: Mapped[WalletKind] = mapped_column(SAEnum(WalletKind), default=WalletKind.REAL)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)  # signed
    balance_after: Mapped[int] = mapped_column(BigInteger, nullable=False)
    reference: Mapped[str] = mapped_column(String(120), default="")
    idempotency_key: Mapped[str] = mapped_column(String(120), unique=True, index=True)

    wallet = relationship("Wallet", back_populates="transactions")
