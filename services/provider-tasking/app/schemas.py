from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime
from uuid import UUID

class Location(BaseModel):
    terminal: Optional[str] = None
    zone: Optional[str] = None
    gate: Optional[str] = None

class Flight(BaseModel):
    iata: Optional[str] = None
    std: Optional[datetime] = None

class ChecklistItem(BaseModel):
    key: str
    title: str
    required: bool = True
    done: bool = False

class TaskCreate(BaseModel):
    order_item_id: str
    service_type: str
    provider_id: Optional[str] = None
    location: Optional[Location] = None
    flight: Optional[Flight] = None
    customer_hint: Optional[dict] = None
    checklist: Optional[List[ChecklistItem]] = None
    sla_due_at: Optional[datetime] = None

class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    order_item_id: str
    service_type: str
    provider_id: Optional[str]
    location: Optional[Location]
    flight: Optional[Flight]
    customer_hint: Optional[dict]
    status: Literal["new","assigned","in_progress","done","failed","cancelled"]
    checklist: Optional[List[ChecklistItem]]
    sla_due_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

class ScanPayload(BaseModel):
    qr_payload: str

class FailPayload(BaseModel):
    reason_code: str
    note: Optional[str] = None
