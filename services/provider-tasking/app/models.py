from sqlalchemy import Column, String, DateTime, Enum, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
import enum

from .db import Base

class TaskStatus(str, enum.Enum):
    new = "new"
    assigned = "assigned"
    in_progress = "in_progress"
    done = "done"
    failed = "failed"
    cancelled = "cancelled"

class Task(Base):
    __tablename__ = "tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    order_item_id = Column(String, nullable=False)
    service_type = Column(String, nullable=False)
    provider_id = Column(String, nullable=True)
    location = Column(JSON, nullable=True)  # {terminal, zone, gate}
    flight = Column(JSON, nullable=True)    # {iata, std}
    customer_hint = Column(JSON, nullable=True)  # {nameMasked, partySize}
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.new)
    checklist = Column(JSON, nullable=True) # [{key,title,required,done}]
    sla_due_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class TaskEvent(Base):
    __tablename__ = "task_events"
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(UUID(as_uuid=True), nullable=False)
    code = Column(String, nullable=False)   # ACCEPTED|STARTED|COMPLETED|FAILED|SCANNED
    payload = Column(JSON, nullable=True)
    ts = Column(DateTime(timezone=True), server_default=func.now())
