"""Direct tests of the exclusion constraint: no service code, just the database saying no."""

from collections.abc import Awaitable, Callable
from datetime import UTC, datetime

import pytest
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Reservation, Resource, User

EXCLUSION_VIOLATION = "23P01"
CHECK_VIOLATION = "23514"


def at(hour: int, minute: int = 0) -> datetime:
    return datetime(2030, 1, 7, hour, minute, tzinfo=UTC)


def slot(start: datetime, end: datetime, bounds: str = "[)") -> Range[datetime]:
    return Range(start, end, bounds=bounds)


async def book(
    session: AsyncSession,
    court: Resource,
    user: User,
    during: Range[datetime],
    status: str = "confirmed",
) -> Reservation:
    reservation = Reservation(resource_id=court.id, user_id=user.id, during=during, status=status)
    session.add(reservation)
    await session.flush()
    return reservation


async def expect_rejected(
    session: AsyncSession, sqlstate: str, action: Callable[[], Awaitable[object]]
) -> IntegrityError:
    """Run `action` inside a savepoint and assert PostgreSQL rejected it with `sqlstate`."""
    with pytest.raises(IntegrityError) as exc:
        async with session.begin_nested():
            await action()
    assert exc.value.orig.sqlstate == sqlstate
    return exc.value


@pytest.mark.parametrize(
    ("start", "end"),
    [
        (at(18), at(19)),  # identical
        (at(18, 30), at(19, 30)),  # overlaps the end
        (at(17, 30), at(18, 30)),  # overlaps the start
        (at(18, 15), at(18, 45)),  # inside
        (at(17), at(20)),  # contains it
    ],
    ids=["identical", "overlaps_end", "overlaps_start", "inside", "contains"],
)
async def test_overlapping_confirmed_reservation_is_rejected(
    session: AsyncSession, court: Resource, user: User, start: datetime, end: datetime
) -> None:
    await book(session, court, user, slot(at(18), at(19)))

    error = await expect_rejected(
        session, EXCLUSION_VIOLATION, lambda: book(session, court, user, slot(start, end))
    )

    assert error.orig.__cause__.constraint_name == "no_overlapping_confirmed"


async def test_back_to_back_reservations_are_allowed(
    session: AsyncSession, court: Resource, user: User
) -> None:
    await book(session, court, user, slot(at(18), at(19)))
    await book(session, court, user, slot(at(19), at(20)))  # starts exactly when the first ends
    await book(session, court, user, slot(at(17), at(18)))  # ends exactly when the first starts


async def test_same_time_on_another_court_is_allowed(
    session: AsyncSession, court: Resource, user: User
) -> None:
    other_court = Resource(name="Court 2")
    session.add(other_court)
    await session.flush()

    await book(session, court, user, slot(at(18), at(19)))
    await book(session, other_court, user, slot(at(18), at(19)))


async def test_cancelled_reservation_does_not_block_the_slot(
    session: AsyncSession, court: Resource, user: User
) -> None:
    await book(session, court, user, slot(at(18), at(19)), status="cancelled")
    await book(session, court, user, slot(at(18), at(19)))


async def test_cancelling_frees_the_slot(
    session: AsyncSession, court: Resource, user: User
) -> None:
    first = await book(session, court, user, slot(at(18), at(19)))
    first.status = "cancelled"
    await session.flush()

    await book(session, court, user, slot(at(18), at(19)))


async def test_cancelled_reservation_cannot_be_revived_over_a_taken_slot(
    session: AsyncSession, court: Resource, user: User
) -> None:
    old = await book(session, court, user, slot(at(18), at(19)), status="cancelled")
    await book(session, court, user, slot(at(18), at(19)))

    async def revive() -> None:
        old.status = "confirmed"
        await session.flush()

    await expect_rejected(session, EXCLUSION_VIOLATION, revive)


@pytest.mark.parametrize(
    "during",
    [
        slot(at(18), at(19), bounds="[]"),
        slot(at(18), at(19), bounds="(]"),
        slot(at(18), at(19), bounds="()"),
        slot(at(18), None),
        slot(None, at(19)),
        slot(at(18), at(18)),  # empty
    ],
    ids=["closed", "open_start", "both_open", "no_end", "no_start", "empty"],
)
async def test_range_must_be_bounded_and_half_open(
    session: AsyncSession, court: Resource, user: User, during: Range[datetime]
) -> None:
    await expect_rejected(session, CHECK_VIOLATION, lambda: book(session, court, user, during))
