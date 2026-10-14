"""`seed-demo`: sample data through the real booking rules, and the pruning of old rows."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reservation, Resource, User
from app.services import demo

NOW = datetime(2030, 6, 12, 15, 0, tzinfo=UTC)


async def count(session: AsyncSession, model) -> int:
    return await session.scalar(select(func.count()).select_from(model))


async def test_seed_creates_courts_players_and_reservations(session: AsyncSession):
    result = await demo.seed(session, now=NOW)

    assert result.courts_created == demo.COURTS
    assert result.players_created == demo.PLAYERS
    # One per player and day, and the per-user limit (3) is never exceeded.
    assert result.reservations_created == demo.PLAYERS * demo.DAYS_AHEAD
    assert await count(session, Reservation) == result.reservations_created


async def test_seed_twice_adds_nothing(session: AsyncSession):
    await demo.seed(session, now=NOW)

    again = await demo.seed(session, now=NOW)

    assert (again.courts_created, again.players_created, again.reservations_created) == (0, 0, 0)


async def test_seed_leaves_existing_courts_alone(session: AsyncSession, court: Resource):
    result = await demo.seed(session, now=NOW)

    assert result.courts_created == 0
    assert await count(session, Resource) == 1


async def test_prune_removes_old_reservations_of_players_but_not_of_admins(
    session: AsyncSession, court: Resource, user: User
):
    boss = User(email="boss@example.com", password_hash="x", name="Boss", role="admin")
    session.add(boss)
    await session.flush()
    long_ago = NOW - timedelta(days=30)
    for hours, owner in enumerate((user, boss)):  # different hours: one court, no overlap
        start = long_ago + timedelta(hours=hours)
        session.add(
            Reservation(
                resource_id=court.id,
                user_id=owner.id,
                during=Range(start, start + timedelta(hours=1), bounds="[)"),
            )
        )
    await session.flush()

    removed = await demo.prune(session, older_than_days=7, now=NOW)

    assert removed == 1
    left = await session.scalars(select(Reservation.user_id))
    assert list(left) == [boss.id]
