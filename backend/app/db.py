from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from .config import settings


class Base(DeclarativeBase):
    pass


engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal: async_sessionmaker[AsyncSession] = async_sessionmaker(
    engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_db() -> AsyncIterator[AsyncSession]:
    async with SessionLocal() as session:
        yield session


def _run_alembic_upgrade() -> None:
    """별도 프로세스에서 호출하기 위한 헬퍼 (start-all.ps1 가 사용)."""

    from pathlib import Path

    from alembic import command
    from alembic.config import Config

    backend_dir = Path(__file__).resolve().parents[1]
    cfg = Config(str(backend_dir / "alembic.ini"))
    command.upgrade(cfg, "head")


async def init_db() -> None:
    """ORM 매퍼 등록만 한다. 스키마 적용은 별도 alembic 명령 (start-all.ps1 또는 수동).

    lifespan 안에서 alembic upgrade 를 호출하는 방식은 환경에 따라 hang 이 재현돼서 제거.
    """

    from . import models  # noqa: F401  - register ORM mappers
