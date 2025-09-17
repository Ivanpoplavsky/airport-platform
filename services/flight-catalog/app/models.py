"""SQLAlchemy models for the flight-catalog service."""

from __future__ import annotations

import uuid
from datetime import datetime

from enum import Enum

from sqlalchemy import JSON, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


class FlightStatus(str, Enum):  # type: ignore[misc]
    """Enumeration of supported flight statuses."""

    SCHEDULED = "SCHEDULED"
    DELAYED = "DELAYED"
    CANCELLED = "CANCELLED"
    DEPARTED = "DEPARTED"
    LANDED = "LANDED"


class Flight(Base):
    """Flight entity stored in the catalogue."""

    __tablename__ = "flights"

    flight_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    iata: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    std: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    sta: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    status_reason: Mapped[str | None] = mapped_column(String(255))
    last_updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    events: Mapped[list["FlightEvent"]] = relationship(back_populates="flight", cascade="all, delete-orphan")


class FlightEvent(Base):
    """Event emitted for flight changes (stored for the MVP)."""

    __tablename__ = "flight_events"

    id: Mapped[uuid.UUID] = mapped_column(default=uuid.uuid4, primary_key=True)
    flight_id: Mapped[str] = mapped_column(ForeignKey("flights.flight_id", ondelete="CASCADE"), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    payload: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    flight: Mapped[Flight] = relationship(back_populates="events")
