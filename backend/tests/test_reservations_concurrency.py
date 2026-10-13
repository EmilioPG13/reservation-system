"""Simultaneous requests against the real database.

These tests commit for real (each request gets its own connection), so they clean up after
themselves instead of relying on the rolled-back session the other tests share.
"""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, time, timedelta
from typing import NamedTuple

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import OpeningHours, Reservation, Resource, User
from app.db.session import get_session
from app.main import app

RACERS = 20


class World(NamedTuple):
    court_id: str
    headers: list[dict[str, str]]  # one per racer, each a different user
    first_slot: datetime


@pytest.fixture
async def world(engine: AsyncEngine, migrated_schema: None) -> AsyncIterator[World]:
    """A court and 20 users, committed, with every request using its own session."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def session_per_request():
        async with factory() as session:
            yield session

    court = Resource(
        name="Race court",
        timezone="UTC",
        opening_hours=[
            OpeningHours(weekday=d, open_time=time(8), close_time=time(22)) for d in range(7)
        ],
    )
    users = [
        User(email=f"racer{i}@example.com", password_hash="x", name=f"Racer {i}")
        for i in range(RACERS)
    ]
    async with factory() as session:
        session.add(court)
        session.add_all(users)
        await session.commit()

    app.dependency_overrides[get_session] = session_per_request
    try:
        yield World(
            court_id=str(court.id),
            headers=[{"Authorization": f"Bearer {create_access_token(str(u.id))}"} for u in users],
            first_slot=(datetime.now(UTC) + timedelta(days=2)).replace(
                hour=10, minute=0, second=0, microsecond=0
            ),
        )
    finally:
        app.dependency_overrides.clear()
        async with factory() as session:
            await session.execute(delete(Reservation).where(Reservation.resource_id == court.id))
            await session.execute(delete(User).where(User.id.in_([u.id for u in users])))
            await session.execute(delete(Resource).where(Resource.id == court.id))
            await session.commit()


async def count_confirmed(engine: AsyncEngine, court_id: str) -> int:
    async with async_sessionmaker(engine)() as session:
        return await session.scalar(
            select(func.count())
            .select_from(Reservation)
            .where(
                Reservation.resource_id == uuid.UUID(court_id), Reservation.status == "confirmed"
            )
        )


async def test_twenty_simultaneous_requests_for_one_slot_produce_exactly_one_booking(
    engine: AsyncEngine, world: World
):
    """The star test: no application check can win this race; the exclusion constraint does."""
    payload = {"resource_id": world.court_id, "starts_at": world.first_slot.isoformat()}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(
            *(client.post("/reservations", json=payload, headers=h) for h in world.headers)
        )

    codes = sorted(r.status_code for r in responses)
    assert codes == [201] + [409] * (RACERS - 1)
    assert await count_confirmed(engine, world.court_id) == 1


async def test_simultaneous_bookings_by_one_user_cannot_pass_the_limit(
    engine: AsyncEngine, world: World
):
    """Counting then inserting would let parallel requests of one user all slip under the limit."""
    limit = settings.max_active_reservations
    attempts = limit + 3
    headers = world.headers[0]

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        responses = await asyncio.gather(
            *(
                client.post(
                    "/reservations",
                    json={
                        "resource_id": world.court_id,
                        "starts_at": (world.first_slot + timedelta(hours=i)).isoformat(),
                    },
                    headers=headers,
                )
                for i in range(attempts)
            )
        )

    codes = sorted(r.status_code for r in responses)
    assert codes == [201] * limit + [422] * (attempts - limit)
    assert await count_confirmed(engine, world.court_id) == limit
