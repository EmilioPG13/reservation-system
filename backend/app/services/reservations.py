"""Booking, cancelling and listing reservations.

Two bookings of the same slot are never refused by a lookup here: `book` inserts and lets the
`no_overlapping_confirmed` exclusion constraint decide, so the answer stays right when two
requests arrive at the same instant.
"""

import uuid
from datetime import date, datetime, timedelta
from typing import NamedTuple
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Blackout, Reservation, Resource, User
from app.services.availability import CONFIRMED, Slot, SlotStatus, build_slots, day_span
from app.services.resources import ResourceNotFound, get_resource

CANCELLED = "cancelled"
EXCLUSION_VIOLATION = "23P01"


class ReservationError(Exception):
    """A booking or cancellation the rules do not allow."""


class NotASlot(ReservationError):
    """The start is not the beginning of a slot of this court (closed day, odd time...)."""


class SlotInPast(ReservationError):
    pass


class SlotBlocked(ReservationError):
    pass


class SlotTaken(ReservationError):
    """Someone else holds a confirmed reservation overlapping this slot."""


class TooManyActiveReservations(ReservationError):
    def __init__(self, limit: int) -> None:
        super().__init__(f"limit of {limit} active reservations reached")
        self.limit = limit


class ReservationNotFound(ReservationError):
    pass


class AlreadyCancelled(ReservationError):
    pass


class CancellationTooLate(ReservationError):
    def __init__(self, hours: int) -> None:
        super().__init__(f"cannot cancel less than {hours} hours before the start")
        self.hours = hours


class DayReservation(NamedTuple):
    reservation: Reservation
    resource: Resource
    user: User


def _slot_at(
    resource: Resource,
    starts_at: datetime,
    blackouts: list[tuple[datetime, datetime]],
    now: datetime,
) -> Slot:
    """The slot of `resource` that starts exactly at `starts_at`, or NotASlot."""
    tz = ZoneInfo(resource.timezone)
    day = starts_at.astimezone(tz).date()
    hours = next((h for h in resource.opening_hours if h.weekday == day.weekday()), None)
    slots = build_slots(
        day=day,
        tz=tz,
        window=(hours.open_time, hours.close_time) if hours else None,
        slot_minutes=resource.slot_minutes,
        blackouts=blackouts,
        bookings=[],  # deliberately empty: the database decides whether the slot is taken
        now=now,
    )
    slot = next((s for s in slots if s.start == starts_at), None)
    if slot is None:
        raise NotASlot
    if slot.status is SlotStatus.PAST:
        raise SlotInPast
    if slot.status is SlotStatus.BLOCKED:
        raise SlotBlocked
    return slot


async def book(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    resource_id: uuid.UUID,
    starts_at: datetime,
    now: datetime,
) -> Reservation:
    """Reserve the slot of `resource_id` that starts at `starts_at`.

    Raises ResourceNotFound, NotASlot, SlotInPast, SlotBlocked, TooManyActiveReservations or
    SlotTaken.
    """
    resource = await get_resource(session, resource_id)
    if not resource.active:
        raise ResourceNotFound

    window = Range(starts_at, starts_at + timedelta(minutes=resource.slot_minutes), bounds="[)")
    blackouts = [
        (during.lower, during.upper)
        for during in await session.scalars(
            select(Blackout.during).where(
                Blackout.resource_id == resource_id, Blackout.during.overlaps(window)
            )
        )
    ]
    slot = _slot_at(resource, starts_at, blackouts, now)

    # The limit is a count followed by an insert, which two requests of the same user could both
    # pass. Locking the user's row makes that user's bookings take turns; other users are not
    # affected.
    await session.execute(select(User.id).where(User.id == user_id).with_for_update())
    active = await session.scalar(
        select(func.count())
        .select_from(Reservation)
        .where(
            Reservation.user_id == user_id,
            Reservation.status == CONFIRMED,
            Reservation.during.overlaps(Range(now, None, bounds="[)")),  # not ended yet
        )
    )
    if active >= settings.max_active_reservations:
        raise TooManyActiveReservations(settings.max_active_reservations)

    reservation = Reservation(
        resource_id=resource_id,
        user_id=user_id,
        during=Range(slot.start, slot.end, bounds="[)"),
        status=CONFIRMED,
        cancelled_at=None,
        reminder_sent_at=None,
    )
    session.add(reservation)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if exc.orig.sqlstate == EXCLUSION_VIOLATION:
            raise SlotTaken from exc
        raise
    return reservation


async def list_for_user(
    session: AsyncSession, user_id: uuid.UUID, *, limit: int, offset: int
) -> tuple[list[Reservation], int]:
    """A page of the user's reservations, latest start first, and how many exist in total."""
    where = Reservation.user_id == user_id
    total = await session.scalar(select(func.count()).select_from(Reservation).where(where))
    page = await session.scalars(
        select(Reservation)
        .where(where)
        .order_by(func.lower(Reservation.during).desc(), Reservation.id)
        .limit(limit)
        .offset(offset)
    )
    return list(page), total


async def list_for_day(session: AsyncSession, day: date) -> list[DayReservation]:
    """Confirmed reservations that start on `day` in their court's zone, with who booked."""
    rows = await session.execute(
        select(Reservation, Resource, User)
        .join(Resource, Reservation.resource_id == Resource.id)
        .join(User, Reservation.user_id == User.id)
        .where(Reservation.status == CONFIRMED, Reservation.during.overlaps(day_span(day)))
        .order_by(Resource.name, func.lower(Reservation.during))
    )
    return [
        DayReservation(reservation, resource, user)
        for reservation, resource, user in rows
        if reservation.during.lower.astimezone(ZoneInfo(resource.timezone)).date() == day
    ]


async def _cancel(
    session: AsyncSession, reservation_id: uuid.UUID, *, owner_id: uuid.UUID | None, now: datetime
) -> Reservation:
    """Cancel a reservation. `owner_id` None is the admin path: any reservation, any time."""
    # Locked so two simultaneous cancellations of the same reservation do not both succeed.
    reservation = await session.scalar(
        select(Reservation).where(Reservation.id == reservation_id).with_for_update()
    )
    # Someone else's reservation looks like a missing one, so ids cannot be probed.
    if reservation is None or (owner_id is not None and reservation.user_id != owner_id):
        raise ReservationNotFound
    if reservation.status == CANCELLED:
        raise AlreadyCancelled
    if owner_id is not None:
        hours = settings.cancellation_window_hours
        if reservation.during.lower - now < timedelta(hours=hours):
            raise CancellationTooLate(hours)

    reservation.status = CANCELLED
    reservation.cancelled_at = now
    await session.commit()
    return reservation


async def cancel_own(
    session: AsyncSession, reservation_id: uuid.UUID, *, user_id: uuid.UUID, now: datetime
) -> Reservation:
    """A user cancels their own reservation, at least `cancellation_window_hours` ahead."""
    return await _cancel(session, reservation_id, owner_id=user_id, now=now)


async def cancel_as_admin(
    session: AsyncSession, reservation_id: uuid.UUID, *, now: datetime
) -> Reservation:
    """An admin cancels any reservation, for example one left under a blackout."""
    return await _cancel(session, reservation_id, owner_id=None, now=now)
