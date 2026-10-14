"""The 24-hour reminder: who gets one, exactly once, and what happens when mail fails."""

import asyncio
import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, time, timedelta
from email.message import EmailMessage

import pytest
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.db.models import OpeningHours, Reservation, Resource, User
from app.services import mailer
from app.workers.reminders import send_due_reminders

# A fixed "now" far from today: the pass takes `now` as an argument, so no clock is involved.
NOW = datetime(2030, 6, 12, 12, tzinfo=UTC)
LONG_AGO = NOW - timedelta(days=5)


def reservation(
    court_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    starts_in: float,
    status: str = "confirmed",
    created_at: datetime = LONG_AGO,
) -> Reservation:
    start = NOW + timedelta(hours=starts_in)
    return Reservation(
        resource_id=court_id,
        user_id=user_id,
        during=Range(start, start + timedelta(hours=1), bounds="[)"),
        status=status,
        created_at=created_at,
    )


@pytest.fixture
async def venue(session: AsyncSession) -> uuid.UUID:
    court = Resource(name="Court Azul", timezone="UTC")
    session.add(court)
    await session.flush()
    return court.id


async def add(session: AsyncSession, *reservations: Reservation) -> None:
    session.add_all(reservations)
    await session.flush()


async def reminded_at(session: AsyncSession, r: Reservation) -> datetime | None:
    await session.refresh(r)
    return r.reminder_sent_at


async def test_a_reservation_inside_the_window_is_reminded(
    session: AsyncSession, user: User, venue: uuid.UUID, outbox: list[EmailMessage]
):
    due = reservation(venue, user.id, starts_in=23)
    await add(session, due)

    assert await send_due_reminders(session, NOW) == 1

    [message] = outbox
    assert message["To"].addresses[0].addr_spec == user.email
    assert message["Subject"].startswith("Reminder: Court Azul")
    assert await reminded_at(session, due) == NOW


async def test_a_reservation_is_reminded_only_once(
    session: AsyncSession, user: User, venue: uuid.UUID, outbox: list[EmailMessage]
):
    await add(session, reservation(venue, user.id, starts_in=23))

    first = await send_due_reminders(session, NOW)
    second = await send_due_reminders(session, NOW + timedelta(minutes=1))

    assert (first, second) == (1, 0)
    assert len(outbox) == 1


async def test_a_reservation_further_ahead_waits_for_its_turn(
    session: AsyncSession, user: User, venue: uuid.UUID, outbox: list[EmailMessage]
):
    later = reservation(venue, user.id, starts_in=30)
    await add(session, later)

    assert await send_due_reminders(session, NOW) == 0
    assert await send_due_reminders(session, NOW + timedelta(hours=7)) == 1  # now 23 hours away
    assert len(outbox) == 1
    assert await reminded_at(session, later) is not None


@pytest.mark.parametrize(
    "case",
    [
        {"starts_in": -1},  # already started
        {"starts_in": 5, "status": "cancelled"},
        {"starts_in": 5, "created_at": NOW - timedelta(hours=1)},  # booked inside the window
    ],
    ids=["already-started", "cancelled", "booked-inside-the-window"],
)
async def test_these_reservations_get_no_reminder(
    session: AsyncSession, user: User, venue: uuid.UUID, outbox: list[EmailMessage], case: dict
):
    skipped = reservation(venue, user.id, **case)
    await add(session, skipped)

    assert await send_due_reminders(session, NOW) == 0
    assert outbox == []
    assert await reminded_at(session, skipped) is None


async def test_a_booking_made_exactly_24_hours_ahead_is_still_reminded(
    session: AsyncSession, user: User, venue: uuid.UUID, outbox: list[EmailMessage]
):
    """The edge of the rule above: created exactly 24 hours before the start still counts."""
    await add(
        session, reservation(venue, user.id, starts_in=5, created_at=NOW - timedelta(hours=19))
    )

    assert await send_due_reminders(session, NOW) == 1


async def test_a_failing_mail_server_loses_the_reminder_instead_of_repeating_it(
    session: AsyncSession,
    user: User,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
    monkeypatch: pytest.MonkeyPatch,
):
    """Marked before sending, on purpose: a lost email is better than a duplicate."""
    due = reservation(venue, user.id, starts_in=23)
    await add(session, due)

    working = mailer.send  # the outbox collector

    async def refuse(message: EmailMessage) -> None:
        raise ConnectionRefusedError("SMTP server is down")

    monkeypatch.setattr(mailer, "send", refuse)

    assert await send_due_reminders(session, NOW) == 0
    assert await reminded_at(session, due) == NOW

    monkeypatch.setattr(mailer, "send", working)  # the server comes back...
    assert await send_due_reminders(session, NOW + timedelta(minutes=1)) == 0  # ...no retry
    assert outbox == []


async def test_one_failing_reminder_does_not_stop_the_others(
    session: AsyncSession,
    user: User,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
    monkeypatch: pytest.MonkeyPatch,
):
    await add(
        session,
        reservation(venue, user.id, starts_in=3),
        reservation(venue, user.id, starts_in=4),
        reservation(venue, user.id, starts_in=5),
    )
    delivered = mailer.send  # the outbox collector
    calls = 0

    async def fail_the_first(message: EmailMessage) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ConnectionResetError
        await delivered(message)

    monkeypatch.setattr(mailer, "send", fail_the_first)

    assert await send_due_reminders(session, NOW) == 2
    assert len(outbox) == 2


# --- simultaneous passes ---------------------------------------------------------------------

PASSES = 4
DUE = 6


@pytest.fixture
async def committed_due(engine: AsyncEngine, migrated_schema: None) -> AsyncIterator[uuid.UUID]:
    """A court with DUE reminders waiting, committed so separate sessions can all see them."""
    factory = async_sessionmaker(engine, expire_on_commit=False)
    court = Resource(
        name="Reminder court",
        timezone="UTC",
        opening_hours=[OpeningHours(weekday=0, open_time=time(8), close_time=time(22))],
    )
    users = [
        User(email=f"reminded{i}@example.com", password_hash="x", name=f"Player {i}")
        for i in range(DUE)
    ]
    async with factory() as session:
        session.add(court)
        session.add_all(users)
        await session.flush()
        session.add_all(reservation(court.id, u.id, starts_in=3 + i) for i, u in enumerate(users))
        await session.commit()
    try:
        yield court.id
    finally:
        async with factory() as session:
            await session.execute(delete(Reservation).where(Reservation.resource_id == court.id))
            await session.execute(delete(User).where(User.id.in_([u.id for u in users])))
            await session.execute(delete(Resource).where(Resource.id == court.id))
            await session.commit()


async def test_overlapping_passes_never_remind_the_same_reservation_twice(
    engine: AsyncEngine, committed_due: uuid.UUID, outbox: list[EmailMessage]
):
    """Two copies of the app, or a slow pass overlapped by the next: each reminder goes out once."""
    factory = async_sessionmaker(engine, expire_on_commit=False)

    async def one_pass() -> int:
        async with factory() as session:
            return await send_due_reminders(session, NOW)

    sent = await asyncio.gather(*(one_pass() for _ in range(PASSES)))

    assert sum(sent) == DUE
    assert len(outbox) == DUE
    assert len({m["To"].addresses[0].addr_spec for m in outbox}) == DUE
    async with factory() as session:
        remaining = await session.scalars(
            select(Reservation.id).where(
                Reservation.resource_id == committed_due, Reservation.reminder_sent_at.is_(None)
            )
        )
        assert list(remaining) == []
