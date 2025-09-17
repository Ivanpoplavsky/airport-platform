from pathlib import Path
import sys

from fastapi.testclient import TestClient

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.main import app, make_passenger_id, make_ticket_hash, mask_passenger_name  # noqa: E402


client = TestClient(app)


def test_mask_passenger_name():
    assert mask_passenger_name("Иванов Иван") == "И*** И."
    assert mask_passenger_name(" Петров  Петр  ") == "П*** П."
    assert mask_passenger_name("") == ""


def test_lookup_is_deterministic():
    payload = {"ticket_or_pnr": "555-1234567890"}
    first = client.post("/lookup", json=payload).json()
    second = client.post("/lookup", json=payload).json()
    assert first == second
    assert first["ticket_hash"] == make_ticket_hash("555-1234567890")
    assert first["passenger_id"] == make_passenger_id("555-1234567890", "Иванов Иван")


def test_lookup_not_found():
    response = client.post("/lookup", json={"ticket_or_pnr": "unknown"})
    assert response.status_code == 404
    assert response.json()["detail"] == "Booking not found"
