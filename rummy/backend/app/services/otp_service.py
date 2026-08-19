"""OTP generation/verification for mobile register, login and password reset.

No SMS gateway is wired up yet (see `Settings.otp_dev_mode`). When dev mode is on,
`send_otp` never calls out to anything — it just persists the code and hands it back
to the caller so the API response (or a log line) can surface it for testing. Swapping
in a real provider later means implementing `_dispatch_sms` and flipping the setting.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.otp import OtpCode, OtpPurpose

logger = logging.getLogger(__name__)


def _generate_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def send_otp(db: Session, phone: str, purpose: OtpPurpose) -> str | None:
    """Create and store a fresh OTP for `phone`, invalidating older unused ones.

    Returns the plaintext code only in dev mode (for the API/tests to surface it
    without a real SMS provider); returns None once a real provider is configured.
    """
    now = datetime.now(timezone.utc)
    (
        db.query(OtpCode)
        .filter(OtpCode.phone == phone, OtpCode.purpose == purpose, OtpCode.consumed_at.is_(None))
        .update({OtpCode.consumed_at: now})
    )
    code = _generate_code()
    db.add(
        OtpCode(
            phone=phone,
            purpose=purpose,
            code=code,
            expires_at=now + timedelta(minutes=settings.otp_expire_minutes),
        )
    )
    db.commit()

    if settings.otp_dev_mode:
        logger.info("DEV OTP for %s (%s): %s", phone, purpose.value, code)
        return code
    _dispatch_sms(phone, code)
    return None


def _dispatch_sms(phone: str, code: str) -> None:  # pragma: no cover - no provider yet
    raise NotImplementedError("No SMS provider configured; set otp_dev_mode=True for local dev")


def verify_otp(db: Session, phone: str, purpose: OtpPurpose, code: str) -> bool:
    """Check `code` against the latest unconsumed, unexpired OTP for `phone`.

    On success the OTP is marked consumed so it can't be replayed.
    """
    now = datetime.now(timezone.utc)
    otp = (
        db.query(OtpCode)
        .filter(
            OtpCode.phone == phone,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
            OtpCode.expires_at > now,
        )
        .order_by(OtpCode.created_at.desc())
        .first()
    )
    if otp is None or not secrets.compare_digest(otp.code, code):
        return False
    otp.consumed_at = now
    db.commit()
    return True
