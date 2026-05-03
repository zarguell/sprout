"""Shared test database infrastructure — engine, sessionmaker.

test_api.py and test_gaps.py import from here. The conftest.py
re-exports fixtures so they're auto-discovered by pytest."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-for-testing-only")

from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.database import get_db
from app.models import Base
from app.main import app

TEST_DB_URL = os.environ["DATABASE_URL"]
_test_engine = create_async_engine(TEST_DB_URL, echo=False)
TestSession = sessionmaker(_test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


app.dependency_overrides[get_db] = override_get_db


@asynccontextmanager
async def setup_db():
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)