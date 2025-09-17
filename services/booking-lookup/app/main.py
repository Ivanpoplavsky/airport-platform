from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, Iterable, List, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger("booking_lookup")
logging.basicConfig(level=logging.INFO)


@dataclass(frozen=True)
class FlightDetails:
    """Domain entity that represents a flight associated with a booking."""

    iata: str
    std: datetime


@dataclass(frozen=True)
class BookingRecord:
    """Domain entity stored in the mock repository."""

    ticket_number: str
    pnr: str
    passenger_name: str
    flight: FlightDetails
    service_suggestions: tuple[str, ...] = ()


class BookingRepository:
    """Simple in-memory repository for the MVP implementation."""

    def __init__(self, records: Iterable[BookingRecord]):
        self._index: Dict[str, BookingRecord] = {}
        for record in records:
            self._index[record.ticket_number] = record
            self._index[record.pnr] = record

    def get(self, identifier: str) -> Optional[BookingRecord]:
        return self._index.get(identifier)


class LookupRequest(BaseModel):
    ticket_or_pnr: str = Field(..., description="Ticket number or PNR to lookup", min_length=1)


class FlightSchema(BaseModel):
    iata: str
    std: datetime


class LookupResponse(BaseModel):
    passenger_id: str
    passenger_masked: str
    ticket_hash: str
    ticket_last4: str
    flight_id: str
    flight: FlightSchema
    service_suggestions: List[str] = []


MOCK_REPOSITORY = BookingRepository(
    records=[
        BookingRecord(
            ticket_number="555-1234567890",
            pnr="ABC123",
            passenger_name="Иванов Иван",
            flight=FlightDetails(iata="SU123", std=datetime.fromisoformat("2025-09-17T10:00:00+00:00")),
            service_suggestions=("WCHR",),
        ),
        BookingRecord(
            ticket_number="555-9876543210",
            pnr="XYZ789",
            passenger_name="Петров Петр",
            flight=FlightDetails(iata="SU321", std=datetime.fromisoformat("2025-11-05T20:15:00+00:00")),
            service_suggestions=(),
        ),
    ]
)

app = FastAPI(title="Booking Lookup Service", version="0.1.0")


def mask_passenger_name(full_name: str) -> str:
    parts = [part for part in full_name.strip().split(" ") if part]
    if not parts:
        return ""

    masked_parts: List[str] = []
    for index, part in enumerate(parts):
        first_letter = part[0]
        if index == 0:
            masked = first_letter + "***" if len(part) > 1 else first_letter
        else:
            masked = f"{first_letter}."
        masked_parts.append(masked)
    return " ".join(masked_parts)


def make_ticket_hash(ticket_number: str) -> str:
    digest = hashlib.sha256(ticket_number.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def make_passenger_id(ticket_number: str, passenger_name: str) -> str:
    digest = hashlib.sha256(f"{ticket_number}|{passenger_name}".encode("utf-8")).hexdigest()
    return f"pax_{digest[:12]}"


def make_flight_id(flight: FlightDetails) -> str:
    digest = hashlib.sha256(f"{flight.iata}|{flight.std.isoformat()}".encode("utf-8")).hexdigest()
    return f"flt_{digest[:12]}"


@app.post("/lookup", response_model=LookupResponse)
def lookup_booking(payload: LookupRequest) -> LookupResponse:
    identifier = payload.ticket_or_pnr.strip()
    logger.info("Lookup requested for identifier=%s", identifier)

    booking = MOCK_REPOSITORY.get(identifier)
    if booking is None:
        logger.error("Booking not found for identifier=%s", identifier)
        raise HTTPException(status_code=404, detail="Booking not found")

    ticket_hash = make_ticket_hash(booking.ticket_number)
    passenger_id = make_passenger_id(booking.ticket_number, booking.passenger_name)
    flight_id = make_flight_id(booking.flight)
    response = LookupResponse(
        passenger_id=passenger_id,
        passenger_masked=mask_passenger_name(booking.passenger_name),
        ticket_hash=ticket_hash,
        ticket_last4=booking.ticket_number[-4:],
        flight_id=flight_id,
        flight=FlightSchema(iata=booking.flight.iata, std=booking.flight.std),
        service_suggestions=list(booking.service_suggestions),
    )

    logger.info("Lookup succeeded for identifier=%s", identifier)
    return response


@app.get("/health")
def health() -> Dict[str, str]:
    """Basic health endpoint for container orchestration."""
    return {"status": "ok"}
