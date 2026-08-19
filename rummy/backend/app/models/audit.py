from __future__ import annotations

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDMixin


class AuditLog(UUIDMixin, TimestampMixin, Base):
    """Append-only record of security/game/money-relevant events."""
    __tablename__ = "audit_logs"

    actor_id: Mapped[str] = mapped_column(String(36), index=True, default="")
    action: Mapped[str] = mapped_column(String(80), nullable=False)
    entity: Mapped[str] = mapped_column(String(80), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    detail_json: Mapped[str] = mapped_column(String, default="{}")
    ip_address: Mapped[str] = mapped_column(String(64), default="")
