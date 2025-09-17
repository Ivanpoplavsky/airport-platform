from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from .models import Task, TaskStatus, TaskEvent
from .schemas import TaskCreate


class InvalidStatusTransition(Exception):
    def __init__(self, current: TaskStatus, new: TaskStatus) -> None:
        self.current = current
        self.new = new
        super().__init__(f"Cannot transition task from {current} to {new}")


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.new: {TaskStatus.assigned, TaskStatus.failed, TaskStatus.cancelled},
    TaskStatus.assigned: {TaskStatus.in_progress, TaskStatus.failed, TaskStatus.cancelled},
    TaskStatus.in_progress: {TaskStatus.done, TaskStatus.failed, TaskStatus.cancelled},
    TaskStatus.done: set(),
    TaskStatus.failed: set(),
    TaskStatus.cancelled: set(),
}

async def create_task(db: AsyncSession, data: TaskCreate) -> Task:
    location_data = data.location.model_dump(mode="json") if data.location else None
    flight_data = data.flight.model_dump(mode="json") if data.flight else None
    checklist_data = (
        [c.model_dump(mode="json") for c in data.checklist]
        if data.checklist is not None
        else None
    )
    provider_id = data.provider_id
    customer_hint_data = data.customer_hint
    sla_due_at = data.sla_due_at

    filters = [
        Task.order_item_id == data.order_item_id,
        Task.service_type == data.service_type,
    ]

    for column, value in [
        (Task.provider_id, provider_id),
        (Task.location, location_data),
        (Task.flight, flight_data),
        (Task.customer_hint, customer_hint_data),
        (Task.checklist, checklist_data),
        (Task.sla_due_at, sla_due_at),
    ]:
        if value is None:
            filters.append(column.is_(None))
        else:
            filters.append(column == value)

    existing_stmt = select(Task).where(*filters)
    existing_res = await db.execute(existing_stmt)
    existing_task = existing_res.scalar_one_or_none()
    if existing_task:
        return existing_task

    task = Task(
        order_item_id=data.order_item_id,
        service_type=data.service_type,
        provider_id=provider_id,
        location=location_data,
        flight=flight_data,
        customer_hint=customer_hint_data,
        checklist=checklist_data,
        sla_due_at=sla_due_at,
    )
    db.add(task)
    await db.flush()
    db.add(TaskEvent(task_id=task.id, code="CREATED", payload=None))
    await db.commit()
    await db.refresh(task)
    return task

async def list_tasks(db: AsyncSession, statuses: List[TaskStatus] | None = None) -> List[Task]:
    stmt = select(Task)
    if statuses:
        stmt = stmt.where(Task.status.in_(statuses))
    res = await db.execute(stmt.order_by(Task.created_at.desc()))
    return list(res.scalars())

async def set_status(
    db: AsyncSession,
    task_id: UUID,
    new_status: TaskStatus,
    event: str,
    payload: dict | None = None,
) -> Task:
    res = await db.execute(select(Task).where(Task.id == task_id).with_for_update())
    task = res.scalar_one()

    if new_status == task.status:
        return task

    allowed_next = ALLOWED_TRANSITIONS.get(task.status, set())
    if new_status not in allowed_next:
        raise InvalidStatusTransition(task.status, new_status)

    task.status = new_status
    event_payload = payload.copy() if payload is not None else None
    db.add(TaskEvent(task_id=task_id, code=event, payload=event_payload))
    await db.commit()
    await db.refresh(task)
    return task
