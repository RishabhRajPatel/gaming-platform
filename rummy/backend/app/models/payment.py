from __future__ import annotations

from enum import Enum

from sqlalchemy import BigInteger, ForeignKey, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class PaymentStatus(str, Enum):
    CREATED = "created"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class WithdrawalStatus(str, Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    PROCESSED = "processed"
    REJECTED = "rejected"


class Deposit(UUIDMixin, TimestampMixin, Base):
    """A Razorpay order for adding real money to the wallet."""
    __tablename__ = "deposits"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[PaymentStatus] = mapped_column(SAEnum(PaymentStatus), default=PaymentStatus.CREATED)
    razorpay_order_id: Mapped[str] = mapped_column(String(64), index=True, default="")
    razorpay_payment_id: Mapped[str] = mapped_column(String(64), default="")


class Withdrawal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "withdrawals"

    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    amount_paise: Mapped[int] = mapped_column(BigInteger, nullable=False)
    status: Mapped[WithdrawalStatus] = mapped_column(
        SAEnum(WithdrawalStatus), default=WithdrawalStatus.REQUESTED
    )
    payout_reference: Mapped[str] = mapped_column(String(120), default="")
