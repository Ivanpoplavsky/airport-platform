from fastapi import FastAPI, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import Any, Callable, List

from .db import SessionLocal, init_db
from . import service
from .service import InvalidStatusTransition
from .models import TaskStatus
from .schemas import TaskCreate, TaskOut, ScanPayload, FailPayload  # FailPayload можно оставить даже если ручки /fail нет

app = FastAPI(title="Provider Tasking", version="0.1.0")


async def get_db():
    async with SessionLocal() as session:
        yield session


@app.on_event("startup")
async def on_startup():
    await init_db()


@app.get("/health")
async def health():
    return {"status": "ok"}


# Список задач для сотрудника
@app.get("/tasks", response_model=List[TaskOut])
async def get_tasks(
    status: List[TaskStatus] = Query(default=[]),
    db: AsyncSession = Depends(get_db),
):
    tasks = await service.list_tasks(db, statuses=status or None)
    return tasks


def _handle_transition_error(exc: InvalidStatusTransition) -> HTTPException:
    """Convert service transition errors into HTTP 409 Conflict responses."""
    return HTTPException(status_code=409, detail=str(exc))


def _model_to_dict(model: object | None) -> dict | None:
    """Вернуть JSON-безопасный dict из Pydantic v2/v1 модели или None."""
    if model is None:
        return None

    # Pydantic v2
    dump_v2: Callable[..., Any] | None = getattr(model, "model_dump", None)
    if callable(dump_v2):
        return dump_v2(mode="json")

    # Pydantic v1 (на всякий случай)
    dump_v1: Callable[..., Any] | None = getattr(model, "dict", None)
    if callable(dump_v1):
        return dump_v1()

    raise TypeError("Unsupported payload type for status transition")


async def _change_status(
    db: AsyncSession,
    task_id: UUID,
    new_status: TaskStatus,
    event: str,
    payload: dict | None = None,
) -> TaskOut:
    try:
        return await service.set_status(db, task_id, new_status, event, payload)
    except InvalidStatusTransition as exc:
        # 409 Conflict при недопустимом переходе статуса
        raise _handle_transition_error(exc) from exc


# Создать задачу (для демонстрации/seed)
@app.post("/tasks", response_model=TaskOut, status_code=201)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    t = await service.create_task(db, payload)
    return t


@app.post("/tasks/{task_id}/accept", response_model=TaskOut)
async def accept_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    return await _change_status(db, task_id, TaskStatus.assigned, "ACCEPTED")


@app.post("/tasks/{task_id}/start", response_model=TaskOut)
async def start_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    return await _change_status(db, task_id, TaskStatus.in_progress, "STARTED")


@app.post("/tasks/{task_id}/scan", response_model=TaskOut)
async def scan_qr(task_id: UUID, payload: ScanPayload, db: AsyncSession = Depends(get_db)):
    payload_data = _model_to_dict(payload)  # JSON-safe
    return await _change_status(db, task_id, TaskStatus.in_progress, "SCANNED", payload_data)
