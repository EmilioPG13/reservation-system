"""Day availability: the opening window cut into slots, minus blackouts and bookings.

`build_slots` is pure time arithmetic with no database, so the edge cases (time zones, DST,
partial slots) are tested as a table. `get_day_availability` loads the rows and feeds it; it runs
four queries however many courts exist, so the grid view needs a single API call.
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Blackout, Reservation, Resource

# Half-open [start, end), like the ranges stored in the database.
type Interval = tuple[datetime, datetime]

CONFIRMED = "confirmed"


class SlotStatus(StrEnum):
    AVAILABLE = "available"
    BOOKED = "booked"
    BLOCKED = "blocked"  # maintenance window
    PAST = "past"  # already started, so it can no longer be booked


@dataclass(frozen=True)
class Slot:
    start: datetime  # always UTC
    end: datetime
    status: SlotStatus


@dataclass(frozen=True)
class CourtDay:
    resource: Resource
    slots: list[Slot]


def _overlaps(start: datetime, end: datetime, intervals: list[Interval]) -> bool:
    return any(start < other_end and other_start < end for other_start, other_end in intervals)


def build_slots(
    *,
    day: date,
    tz: ZoneInfo,
    window: tuple[time, time] | None,
    slot_minutes: int,
    blackouts: list[Interval],
    bookings: list[Interval],
    now: datetime,
) -> list[Slot]:
    """Slots of the local calendar `day`, in UTC, with the status of each.

    `window` is the opening window in the court's local time (None means closed that day).
    Slots are stepped in UTC, so a day with a clock change simply has fewer or more real hours.
    A tail shorter than `slot_minutes` is dropped rather than offered as a short slot.
    """
    if window is None:
        return []
    opens = datetime.combine(day, window[0], tzinfo=tz).astimezone(UTC)
    closes = datetime.combine(day, window[1], tzinfo=tz).astimezone(UTC)
    step = timedelta(minutes=slot_minutes)

    slots: list[Slot] = []
    start = opens
    while start + step <= closes:
        end = start + step
        if _overlaps(start, end, bookings):
            status = SlotStatus.BOOKED
        elif _overlaps(start, end, blackouts):
            status = SlotStatus.BLOCKED
        elif start < now:
            status = SlotStatus.PAST
        else:
            status = SlotStatus.AVAILABLE
        slots.append(Slot(start, end, status))
        start = end
    return slots


def _intervals(ranges: list[Range[datetime]]) -> list[Interval]:
    return [(r.lower, r.upper) for r in ranges]


async def get_day_availability(
    session: AsyncSession, *, day: date, now: datetime
) -> list[CourtDay]:
    """Every active court with its slots for `day`, read in the court's own time zone."""
    resources = list(
        await session.scalars(select(Resource).where(Resource.active).order_by(Resource.name))
    )
    if not resources:
        return []

    # Courts live in different zones, so fetch a UTC span wider than any local day (UTC-12 to
    # UTC+14) and let build_slots do the exact cut.
    midnight = datetime.combine(day, time.min, tzinfo=UTC)
    span = Range(midnight - timedelta(days=1), midnight + timedelta(days=2), bounds="[)")
    ids = [r.id for r in resources]

    blackouts: dict = defaultdict(list)
    for resource_id, during in await session.execute(
        select(Blackout.resource_id, Blackout.during).where(
            Blackout.resource_id.in_(ids), Blackout.during.overlaps(span)
        )
    ):
        blackouts[resource_id].append(during)

    bookings: dict = defaultdict(list)
    for resource_id, during in await session.execute(
        select(Reservation.resource_id, Reservation.during).where(
            Reservation.resource_id.in_(ids),
            Reservation.status == CONFIRMED,
            Reservation.during.overlaps(span),
        )
    ):
        bookings[resource_id].append(during)

    courts = []
    for resource in resources:
        hours = next((h for h in resource.opening_hours if h.weekday == day.weekday()), None)
        slots = build_slots(
            day=day,
            tz=ZoneInfo(resource.timezone),
            window=(hours.open_time, hours.close_time) if hours else None,
            slot_minutes=resource.slot_minutes,
            blackouts=_intervals(blackouts[resource.id]),
            bookings=_intervals(bookings[resource.id]),
            now=now,
        )
        courts.append(CourtDay(resource, slots))
    return courts
