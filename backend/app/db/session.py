from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings

# A transaction-mode pooler hands each statement to any server connection, so asyncpg's cached
# prepared statements would not exist there.
_connect_args = {"statement_cache_size": 0} if settings.database_pooled else {}
engine = create_async_engine(settings.database_url, connect_args=_connect_args)
SessionFactory = async_sessionmaker(engine, expire_on_commit=False)


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: one session per request. Services decide when to commit."""
    async with SessionFactory() as session:
        yield session
