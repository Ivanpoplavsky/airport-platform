"""Database utilities for the flight-catalog service."""

from __future__ import annotations

import os

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase


DEFAULT_DB_USER = "airport"
DEFAULT_DB_PASSWORD = "airport"
DEFAULT_DB_HOST = "localhost"
DEFAULT_DB_PORT = "5432"
DEFAULT_DB_NAME = "airport"


def _build_default_dsn() -> str:
    user = os.getenv("DB_USER", DEFAULT_DB_USER)
    password = os.getenv("DB_PASSWORD", DEFAULT_DB_PASSWORD)
    host = os.getenv("DB_HOST", DEFAULT_DB_HOST)
    port = os.getenv("DB_PORT", DEFAULT_DB_PORT)
    name = os.getenv("DB_NAME", DEFAULT_DB_NAME)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{name}"


def get_database_dsn() -> str:
    """Return the database DSN configured via environment or defaults."""

    return os.getenv("DB_DSN", _build_default_dsn())


engine = create_async_engine(get_database_dsn(), pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""

    pass


async def init_db() -> None:
    """Create database tables for the MVP if they are missing."""

    from . import models  # noqa: F401  ensure metadata is imported

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
