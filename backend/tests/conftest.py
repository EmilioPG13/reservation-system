from collections.abc import AsyncIterator
from email.message import EmailMessage
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Resource, User
from app.db.session import get_session
from app.main import app
from app.services import mailer

BACKEND_DIR = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def outbox(monkeypatch: pytest.MonkeyPatch) -> list[EmailMessage]:
    """Every email the code under test sends; nothing reaches SMTP unless a test says so."""
    sent: list[EmailMessage] = []

    async def collect(message: EmailMessage) -> None:
        sent.append(message)

    monkeypatch.setattr(mailer, "send", collect)
    return sent


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


@pytest.fixture(scope="session")
def alembic_config() -> Config:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    cfg.set_main_option("sqlalchemy.url", settings.test_database_url)
    return cfg


@pytest.fixture(scope="session")
def migrated_schema(alembic_config: Config) -> None:
    """Rebuild the test database schema from the migrations, exercising both directions."""
    command.downgrade(alembic_config, "base")
    command.upgrade(alembic_config, "head")


@pytest.fixture
async def session(engine: AsyncEngine, migrated_schema: None) -> AsyncIterator[AsyncSession]:
    """A session whose work is rolled back at the end, so tests never leak rows."""
    async with engine.connect() as conn:
        outer = await conn.begin()
        # Savepoint mode: a failed flush rolls back only its savepoint, not the whole test.
        async with AsyncSession(
            bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
        ) as s:  # expire_on_commit matches app.db.session.SessionFactory
            yield s
        await outer.rollback()


@pytest.fixture
async def api_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """HTTP client whose requests share the rolled-back test session, so nothing leaks."""

    async def _session() -> AsyncIterator[AsyncSession]:
        yield session

    app.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
async def user(session: AsyncSession) -> User:
    u = User(email="player@example.com", password_hash="x", name="Player")
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
async def court(session: AsyncSession) -> Resource:
    r = Resource(name="Court 1")
    session.add(r)
    await session.flush()
    return r


@pytest.fixture
def user_headers(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(user.id))}"}


@pytest.fixture
async def admin_headers(session: AsyncSession) -> dict[str, str]:
    boss = User(email="boss@example.com", password_hash="x", name="Boss", role="admin")
    session.add(boss)
    await session.flush()
    return {"Authorization": f"Bearer {create_access_token(str(boss.id))}"}
