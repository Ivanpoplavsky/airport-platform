from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase
import os

DB_DSN = (
    f"postgresql+asyncpg://{os.getenv('DB_USER','airport')}:{os.getenv('DB_PASSWORD','airport')}"
    f"@{os.getenv('DB_HOST','localhost')}:{os.getenv('DB_PORT','5432')}/{os.getenv('DB_NAME','airport')}"
)

engine = create_async_engine(DB_DSN, pool_pre_ping=True)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

class Base(DeclarativeBase):
    pass

async def init_db():
    from . import models  # noqa: F401 (регистрация метаданных)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
