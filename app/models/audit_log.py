"""AuditLog SQLAlchemy model."""
from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import DateTime, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import Base


class Action(str, enum.Enum):
    SEND_OTP = "SEND_OTP"
    VERIFY_OTP = "VERIFY_OTP"
    RESET_PASSWORD = "RESET_PASSWORD"


class Outcome(str, enum.Enum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(Enum(Action), nullable=False)
    outcome: Mapped[str] = mapped_column(Enum(Outcome), nullable=False)
    username: Mapped[str | None] = mapped_column(String(256), nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    detail: Mapped[str | None] = mapped_column(String(512), nullable=True)
