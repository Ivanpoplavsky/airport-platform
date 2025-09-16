from fastapi import FastAPI, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from .db import SessionLocal, init_db
from . import service
from .models import TaskStatus
from .schemas import TaskCreate, TaskOut, ScanPayload, FailPayload

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
async def get_tasks(status: List[TaskStatus] = Query(default=[]), db: AsyncSession = Depends(get_db)):
    tasks = await service.list_tasks(db, statuses=status or None)
    return tasks

# Создать задачу (для демонстрации/seed)
@app.post("/tasks", response_model=TaskOut, status_code=201)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)):
    t = await service.create_task(db, payload)
    return t

@app.post("/tasks/{task_id}/accept", response_model=TaskOut)
async def accept_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    t = await service.set_status(db, task_id, TaskStatus.assigned, "ACCEPTED")
    return t

@app.post("/tasks/{task_id}/start", response_model=TaskOut)
async def start_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    t = await service.set_status(db, task_id, TaskStatus.in_progress, "STARTED")
    return t

@app.post("/tasks/{task_id}/scan", response_model=TaskOut)
async def scan_qr(task_id: UUID, payload: ScanPayload, db: AsyncSession = Depends(get_db)):
    t = await service.set_status(db, task_id, TaskStatus.in_progress, "SCANNED", payload.model_dump())
    return t

@app.post("/tasks/{task_id}/complete", response_model=TaskOut)
async def complete_task(task_id: UUID, db: AsyncSession = Depends(get_db)):
    t = await service.set_status(db, task_id, TaskStatus.done, "COMPLETED")
    return t

@app.post("/tasks/{task_id}/fail", response_model=TaskOut)
async def fail_task(task_id: UUID, payload: FailPayload, db: AsyncSession = Depends(get_db)):
    t = await service.set_status(db, task_id, TaskStatus.failed, "FAILED", payload.model_dump())
    return t
