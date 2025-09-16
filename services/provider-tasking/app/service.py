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
    TaskStatus.new: {TaskStatus.assigned, TaskStatus.failed},
    TaskStatus.assigned: {TaskStatus.in_progress, TaskStatus.failed},
    TaskStatus.in_progress: {TaskStatus.done, TaskStatus.failed},
    TaskStatus.done: set(),
    TaskStatus.failed: set(),
}

async def create_task(db: AsyncSession, data: TaskCreate) -> Task:
    location_payload = data.location.model_dump(mode="json") if data.location else None
    flight_payload = data.flight.model_dump(mode="json") if data.flight else None
    checklist_payload = [c.model_dump(mode="json") for c in (data.checklist or [])]

    existing_stmt = select(Task).where(
        Task.order_item_id == data.order_item_id,
        Task.service_type == data.service_type,
    )
    existing_res = await db.execute(existing_stmt)
    for existing_task in existing_res.scalars():
        if (
            existing_task.provider_id == data.provider_id
            and existing_task.location == location_payload
            and existing_task.flight == flight_payload
            and existing_task.customer_hint == data.customer_hint
            and existing_task.checklist == checklist_payload
            and existing_task.sla_due_at == data.sla_due_at
        ):
            return existing_task

    task = Task(
        order_item_id=data.order_item_id,
        service_type=data.service_type,
        provider_id=data.provider_id,
        location=location_payload,
        flight=flight_payload,
        customer_hint=data.customer_hint,
        checklist=checklist_payload,
        sla_due_at=data.sla_due_at,
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
    db.add(TaskEvent(task_id=task_id, code=event, payload=payload))
    await db.commit()
    await db.refresh(task)
    return task
