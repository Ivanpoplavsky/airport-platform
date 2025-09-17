"""Domain services for managing flights and events."""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Flight, FlightEvent, FlightStatus
from .schemas import FlightUpsertRequest


def make_flight_id(iata: str, std: datetime) -> str:
    """Derive a stable flight identifier from IATA code and STD."""

    digest = hashlib.sha256(f"{iata}|{std.isoformat()}".encode("utf-8")).hexdigest()
    return f"flt_{digest[:12]}"


async def get_flight(db: AsyncSession, flight_id: str) -> Optional[Flight]:
    return await db.get(Flight, flight_id)


async def search_flights(db: AsyncSession, iata: str, flight_date: date) -> list[Flight]:
    start = datetime.combine(flight_date, datetime.min.time(), tzinfo=timezone.utc)
    end = datetime.combine(flight_date, datetime.max.time(), tzinfo=timezone.utc)
    stmt = (
        select(Flight)
        .where(
            and_(
                Flight.iata == iata,
                Flight.std >= start,
                Flight.std <= end,
            )
        )
        .order_by(Flight.std.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


def _json_safe(value: object | None) -> object | None:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, FlightStatus):
        return value.value
    return value


def _detect_changes(old: Flight, new_data: FlightUpsertRequest) -> dict:
    """Return a mapping of changed fields with old/new values."""

    changes: dict[str, dict[str, object | None]] = {}
    tracked_fields = ("iata", "std", "sta", "status", "status_reason")
    for field in tracked_fields:
        old_value = getattr(old, field)
        new_value = getattr(new_data, field)
        if field == "status" and new_value is not None:
            new_value = new_value.value
        if old_value != new_value:
            changes[field] = {
                "old": _json_safe(old_value),
                "new": _json_safe(new_value),
            }
    return changes


async def upsert_flight(db: AsyncSession, payload: FlightUpsertRequest) -> tuple[Flight, str | None]:
    """Create or update a flight and register an event for the change."""

    flight_id = payload.flight_id or make_flight_id(payload.iata, payload.std)
    now = datetime.now(timezone.utc)

    flight = await get_flight(db, flight_id)
    event_type: str | None = None
    event_payload: dict[str, object | None] | None = None

    if flight is None:
        flight = Flight(
            flight_id=flight_id,
            iata=payload.iata,
            std=payload.std,
            sta=payload.sta,
            status=payload.status.value,
            status_reason=payload.status_reason,
            last_updated_at=now,
        )
        db.add(flight)
        event_type = "flight.created"
        event_payload = {
            "flight_id": flight_id,
            "iata": payload.iata,
            "std": payload.std.isoformat(),
            "sta": payload.sta.isoformat() if payload.sta else None,
            "status": payload.status.value,
            "status_reason": payload.status_reason,
        }
    else:
        changes = _detect_changes(flight, payload)
        if changes:
            previous_status = flight.status
            flight.iata = payload.iata
            flight.std = payload.std
            flight.sta = payload.sta
            flight.status = payload.status.value
            flight.status_reason = payload.status_reason
            flight.last_updated_at = now

            if previous_status != FlightStatus.CANCELLED.value and payload.status is FlightStatus.CANCELLED:
                event_type = "flight.cancelled"
                event_payload = {
                    "flight_id": flight_id,
                    "previous_status": previous_status,
                    "status": payload.status.value,
                    "status_reason": payload.status_reason,
                }
            else:
                event_type = "flight.updated"
                event_payload = {
                    "flight_id": flight_id,
                    "changes": changes,
                }
        else:
            flight.last_updated_at = now

    flight.last_updated_at = now

    if event_type is not None:
        event = FlightEvent(
            flight_id=flight_id,
            event_type=event_type,
            payload=event_payload,
            created_at=now,
        )
        db.add(event)

    await db.commit()
    await db.refresh(flight)
    return flight, event_type
