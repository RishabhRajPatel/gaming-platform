from __future__ import annotations

from datetime import datetime
from enum import Enum

from sqlalchemy import DateTime, String
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class OtpPurpose(str, Enum):
    REGISTER = "register"
    RESET_PASSWORD = "reset_password"


class OtpCode(UUIDMixin, TimestampMixin, Base):
    """A one-time code sent to a phone number for register / password-reset.

    `code` is stored in plain text: OTPs are short-lived, single-use, and only ever
    compared server-side, so hashing buys nothing extra here versus a hard expiry
    + consumed flag.
    """

    __tablename__ = "otp_codes"

    phone: Mapped[str] = mapped_column(String(15), index=True, nullable=False)
    purpose: Mapped[OtpPurpose] = mapped_column(SAEnum(OtpPurpose), nullable=False)
    code: Mapped[str] = mapped_column(String(6), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
