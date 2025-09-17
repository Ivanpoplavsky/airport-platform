"""Pydantic schemas for the flight-catalog service."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, Field

from .models import FlightStatus


class FlightBase(BaseModel):
    iata: str = Field(..., description="Flight IATA code", min_length=2)
    std: datetime = Field(..., description="Scheduled time of departure")
    sta: Optional[datetime] = Field(None, description="Scheduled time of arrival")
    status: FlightStatus = Field(..., description="Current status of the flight")
    status_reason: Optional[str] = Field(
        None, description="Optional reason for the current flight status"
    )


class FlightUpsertRequest(FlightBase):
    flight_id: Optional[str] = Field(
        default=None,
        description="Internal flight identifier. If omitted it will be derived from IATA+STD.",
    )


class FlightResponse(FlightBase):
    flight_id: str
    last_updated_at: datetime


class FlightSearchQuery(BaseModel):
    iata: str
    date: date


class FlightEventResponse(BaseModel):
    id: str
    flight_id: str
    event_type: str
    payload: dict | None
    created_at: datetime


class UpsertResult(BaseModel):
    flight: FlightResponse
    event_type: str | None
