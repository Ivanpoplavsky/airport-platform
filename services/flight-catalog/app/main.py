"""FastAPI application exposing the flight-catalog API."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import List, Optional

from fastapi import Depends, FastAPI, HTTPException, Query

from .db import SessionLocal, init_db
from .models import Flight
from .schemas import FlightResponse, FlightUpsertRequest
from .service import get_flight, search_flights, upsert_flight

app = FastAPI(title="Flight Catalog", version="0.1.0")


async def get_db():
    async with SessionLocal() as session:
        yield session


@app.on_event("startup")
async def on_startup() -> None:
    await init_db()


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


def _ensure_timezone(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if getattr(dt, "tzinfo", None) is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _to_response_model(flight: Flight) -> FlightResponse:
    return FlightResponse(
        flight_id=flight.flight_id,
        iata=flight.iata,
        std=_ensure_timezone(flight.std),
        sta=_ensure_timezone(flight.sta),
        status=flight.status,
        status_reason=flight.status_reason,
        last_updated_at=_ensure_timezone(flight.last_updated_at),
    )


@app.get("/flights/{flight_id}", response_model=FlightResponse)
async def get_flight_by_id(flight_id: str, db=Depends(get_db)) -> FlightResponse:
    flight = await get_flight(db, flight_id)
    if flight is None:
        raise HTTPException(status_code=404, detail="Flight not found")
    return _to_response_model(flight)


@app.get("/flights", response_model=List[FlightResponse])
async def find_flights(
    iata: str = Query(..., description="Flight IATA code"),
    date_value: date = Query(..., alias="date", description="STD date (UTC)"),
    db=Depends(get_db),
) -> List[FlightResponse]:
    flights = await search_flights(db, iata, date_value)
    return [_to_response_model(f) for f in flights]


@app.post("/flights", response_model=FlightResponse)
async def create_or_update_flight(payload: FlightUpsertRequest, db=Depends(get_db)) -> FlightResponse:
    flight, _ = await upsert_flight(db, payload)
    return _to_response_model(flight)


