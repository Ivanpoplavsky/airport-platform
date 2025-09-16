from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from .models import Task, TaskStatus, TaskEvent
from .schemas import TaskCreate

async def create_task(db: AsyncSession, data: TaskCreate) -> Task:
    task = Task(
        order_item_id=data.order_item_id,
        service_type=data.service_type,
        provider_id=data.provider_id,
        location=data.location.model_dump() if data.location else None,
        flight=data.flight.model_dump() if data.flight else None,
        customer_hint=data.customer_hint,
        checklist=[c.model_dump() for c in (data.checklist or [])],
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

async def set_status(db: AsyncSession, task_id: UUID, new_status: TaskStatus, event: str, payload: dict | None = None) -> Task:
    await db.execute(update(Task).where(Task.id==task_id).values(status=new_status))
    db.add(TaskEvent(task_id=task_id, code=event, payload=payload))
    await db.commit()
    res = await db.execute(select(Task).where(Task.id==task_id))
    return res.scalar_one()
