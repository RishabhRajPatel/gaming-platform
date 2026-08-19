from __future__ import annotations

from enum import Enum
from typing import Optional

from sqlalchemy import Boolean, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDMixin


class UserRole(str, Enum):
    PLAYER = "player"
    ADMIN = "admin"
    SUPPORT = "support"


class KYCStatus(str, Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    REJECTED = "rejected"


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    # Two supported identities: legacy email/password, and mobile+OTP (main site).
    # Exactly one of email/phone is required at the DB level via a check constraint
    # would be ideal, but SQLite (tests) doesn't enforce those the same way — the API
    # layer guarantees one is always set on create.
    email: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(15), unique=True, index=True, nullable=True)
    username: Mapped[str] = mapped_column(String(40), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.PLAYER)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_18_plus: Mapped[bool] = mapped_column(Boolean, default=False)
    kyc_status: Mapped[KYCStatus] = mapped_column(SAEnum(KYCStatus), default=KYCStatus.UNVERIFIED)

    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
