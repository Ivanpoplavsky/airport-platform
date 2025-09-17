"""Integration tests for the flight-catalog FastAPI service."""

from __future__ import annotations

import importlib
import sys
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

SERVICE_ROOT = Path(__file__).resolve().parents[1]
if str(SERVICE_ROOT) not in sys.path:
    sys.path.append(str(SERVICE_ROOT))

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def app_context(monkeypatch, tmp_path):
    db_path = tmp_path / "flights.sqlite"
    monkeypatch.setenv("DB_DSN", f"sqlite+aiosqlite:///{db_path}")

    for module in ["app.models", "app.db", "app.main"]:
        if module in sys.modules:
            del sys.modules[module]

    app_main = importlib.import_module("app.main")
    app_db = importlib.import_module("app.db")
    app_models = importlib.import_module("app.models")

    return app_main.app, app_db.SessionLocal, app_models.FlightEvent


@pytest_asyncio.fixture()
async def client(app_context):
    app, _, _ = app_context
    async with LifespanManager(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client


async def test_create_and_fetch_flight(app_context, client):
    _, _, _ = app_context

    payload = {
        "iata": "SU123",
        "std": "2025-09-17T10:00:00+00:00",
        "sta": "2025-09-17T12:00:00+00:00",
        "status": "SCHEDULED",
        "status_reason": None,
    }
    response = await client.post("/flights", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["iata"] == "SU123"
    assert data["status"] == "SCHEDULED"

    flight_id = data["flight_id"]
    response = await client.get(f"/flights/{flight_id}")
    assert response.status_code == 200
    fetched = response.json()
    assert fetched["flight_id"] == flight_id
    assert datetime.fromisoformat(fetched["sta"].replace("Z", "+00:00")) == datetime.fromisoformat(
        "2025-09-17T12:00:00+00:00"
    )

    search_response = await client.get(
        "/flights", params={"iata": "SU123", "date": "2025-09-17"}
    )
    assert search_response.status_code == 200
    results = search_response.json()
    assert len(results) == 1
    assert results[0]["flight_id"] == flight_id


async def test_update_creates_cancel_event(app_context, client):
    _, session_factory, event_model = app_context

    payload = {
        "iata": "SU777",
        "std": "2025-12-24T18:00:00+00:00",
        "sta": None,
        "status": "SCHEDULED",
        "status_reason": None,
    }
    create_response = await client.post("/flights", json=payload)
    assert create_response.status_code == 200
    flight_id = create_response.json()["flight_id"]

    update_payload = {
        **payload,
        "flight_id": flight_id,
        "status": "CANCELLED",
        "status_reason": "WEATHER",
    }
    update_response = await client.post("/flights", json=update_payload)
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "CANCELLED"

    async with session_factory() as session:
        result = await session.execute(select(event_model).order_by(event_model.created_at))
        events = list(result.scalars())
        assert len(events) == 2
        assert events[-1].event_type == "flight.cancelled"
        assert events[-1].payload["status_reason"] == "WEATHER"
