from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.main import app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    """Engine bound to the test database (never the development one)."""
    eng = create_async_engine(settings.test_database_url, poolclass=NullPool)
    yield eng
    await eng.dispose()
