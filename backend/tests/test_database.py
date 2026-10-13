from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def test_test_database_is_reachable(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        assert (await conn.scalar(text("SELECT 1"))) == 1


async def test_test_database_is_not_the_dev_one(engine: AsyncEngine) -> None:
    async with engine.connect() as conn:
        assert (await conn.scalar(text("SELECT current_database()"))) == "court_booking_test"


async def test_btree_gist_is_available(engine: AsyncEngine) -> None:
    """Phase 1 needs this extension for the exclusion constraint."""
    async with engine.connect() as conn:
        available = await conn.scalar(
            text("SELECT count(*) FROM pg_available_extensions WHERE name = 'btree_gist'")
        )
    assert available == 1
