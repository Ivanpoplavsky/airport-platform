from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Tuple
from uuid import UUID

from pydantic.json import pydantic_encoder
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from .models import Task, TaskEvent, TaskStatus
from .schemas import TaskCreate


class InvalidStatusTransition(Exception):
    def __init__(self, current: TaskStatus, new: TaskStatus) -> None:
        self.current = current
        self.new = new
        super().__init__(f"Cannot transition task from {current} to {new}")


# Разрешённые переходы статусов (без "cancelled", если такого статуса нет в Enum)
ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.new: {TaskStatus.assigned, TaskStatus.failed},
    TaskStatus.assigned: {TaskStatus.in_progress, TaskStatus.failed},
    TaskStatus.in_progress: {TaskStatus.done, TaskStatus.failed},
    TaskStatus.done: set(),
    TaskStatus.failed: set(),
}


# --- Вспомогательные функции -------------------------------------------------

def _jsonable(value: Any) -> Any:
    """Преобразовать значение в JSON-безопасный объект (dict/list/primitive/None)."""
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return value
    # pydantic_encoder корректно сериализует datetimes и pydantic-модели
    return json.loads(json.dumps(value, default=pydantic_encoder))


def _payload_signature(
    *,
    provider_id: str | None,
    location: Any,
    flight: Any,
    customer_hint: Any,
    checklist: Any,
    sla_due_at: datetime | None,
) -> Tuple[str | None, str, str, str, str, datetime | None]:
    """Нормализованная сигнатура полезной нагрузки для сравнения дублей.

    JSON-поля приводим к стабильной строке (sort_keys=True), чтобы сравнение
    происходило в Python и не требовало операторов равенства для JSON в PG.
    """
    def _dump(value: Any) -> str:
        if value is None:
            return "null"
        return json.dumps(value, default=pydantic_encoder, sort_keys=True)

    return (
        provider_id,
        _dump(location),
        _dump(flight),
        _dump(customer_hint),
        _dump(checklist or []),
        sla_due_at,
    )


# --- Сервисные функции -------------------------------------------------------

async def create_task(db: AsyncSession, data: TaskCreate) -> Task:
    # Приводим поля к JSON-безопасному виду заранее
    location_payload = _jsonable(data.location)
    flight_payload = _jsonable(data.flight)
    checklist_payload = _jsonable(data.checklist or [])
    customer_hint_payload = _jsonable(data.customer_hint)

    # Ищем потенциальные дубли только по стабильным простым полям
    existing_stmt = select(Task).where(
        Task.order_item_id == data.order_item_id,
        Task.service_type == data.service_type,
    )
    existing_res = await db.execute(existing_stmt)

    # Сигнатура новой задачи
    new_signature = _payload_signature(
        provider_id=data.provider_id,
        location=location_payload,
        flight=flight_payload,
        customer_hint=customer_hint_payload,
        checklist=checklist_payload,
        sla_due_at=data.sla_due_at,
    )

    # Сравниваем сигнатуры в Python (без json = json в SQL)
    for existing_task in existing_res.scalars():
        if (
            _payload_signature(
                provider_id=existing_task.provider_id,
                location=existing_task.location,
                flight=existing_task.flight,
                customer_hint=existing_task.customer_hint,
                checklist=existing_task.checklist or [],
                sla_due_at=existing_task.sla_due_at,
            )
            == new_signature
        ):
            return existing_task

    # Создаём новую задачу
    task = Task(
        order_item_id=data.order_item_id,
        service_type=data.service_type,
        provider_id=data.provider_id,
        location=location_payload,
        flight=flight_payload,
        customer_hint=customer_hint_payload,
        checklist=checklist_payload,
        sla_due_at=data.sla_due_at,
    )
    db.add(task)
    await db.flush()

    # Лог события создания
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
    db.add(TaskEvent(task_id=task_id, code=event, payload=_jsonable(payload)))

    await db.commit()
    await db.refresh(task)
    return task
