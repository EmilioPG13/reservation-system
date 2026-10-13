"""Slot arithmetic as a table of cases: no database, only `build_slots`."""

from datetime import UTC, date, datetime, time
from zoneinfo import ZoneInfo

import pytest

from app.services.availability import Interval, SlotStatus, build_slots

MX = ZoneInfo("America/Mexico_City")  # UTC-6 all year since 2022
NEW_YORK = ZoneInfo("America/New_York")
DAY = date(2026, 10, 14)
LONG_AGO = datetime(2026, 1, 1, tzinfo=UTC)

A, B, K, P = SlotStatus.AVAILABLE, SlotStatus.BOOKED, SlotStatus.BLOCKED, SlotStatus.PAST


def mx(hour: int, minute: int = 0) -> datetime:
    """A moment on DAY expressed in Mexico City time, returned in UTC."""
    return datetime(2026, 10, 14, hour, minute, tzinfo=MX).astimezone(UTC)


def slots_for(
    *,
    window: tuple[time, time] | None = (time(18), time(21)),
    slot_minutes: int = 60,
    blackouts: list[Interval] | None = None,
    bookings: list[Interval] | None = None,
    now: datetime = LONG_AGO,
    day: date = DAY,
    tz: ZoneInfo = MX,
):
    return build_slots(
        day=day,
        tz=tz,
        window=window,
        slot_minutes=slot_minutes,
        blackouts=blackouts or [],
        bookings=bookings or [],
        now=now,
    )


def statuses(slots) -> list[SlotStatus]:
    return [s.status for s in slots]


# --- the shape of the day -------------------------------------------------------------------


def test_a_day_without_opening_hours_has_no_slots():
    assert slots_for(window=None) == []


def test_the_window_is_cut_into_consecutive_slots():
    slots = slots_for()

    assert [(s.start, s.end) for s in slots] == [
        (mx(18), mx(19)),
        (mx(19), mx(20)),
        (mx(20), mx(21)),
    ]
    assert statuses(slots) == [A, A, A]


def test_slots_are_returned_in_utc():
    assert all(s.start.utcoffset().total_seconds() == 0 for s in slots_for())


def test_a_late_evening_in_mexico_falls_on_the_next_utc_day():
    """20:00 local is 02:00 UTC of the following date: the day is the local one, not UTC's."""
    slots = slots_for(window=(time(20), time(22)))

    assert slots[0].start == datetime(2026, 10, 15, 2, tzinfo=UTC)
    assert slots[0].start.date() != DAY


def test_a_tail_shorter_than_a_slot_is_dropped():
    assert len(slots_for(window=(time(18), time(20, 30)))) == 2


def test_the_slot_length_comes_from_the_court():
    slots = slots_for(window=(time(9), time(12)), slot_minutes=90)

    assert [(s.start, s.end) for s in slots] == [(mx(9), mx(10, 30)), (mx(10, 30), mx(12))]


# --- bookings and blackouts ------------------------------------------------------------------


def test_a_confirmed_booking_takes_exactly_its_slot():
    assert statuses(slots_for(bookings=[(mx(19), mx(20))])) == [A, B, A]


def test_back_to_back_bookings_do_not_spill_into_neighbours():
    """Ranges are [start, end): a booking ending at 19:00 leaves the 19:00 slot free."""
    assert statuses(slots_for(bookings=[(mx(18), mx(19))])) == [B, A, A]


def test_a_booking_off_the_slot_grid_takes_every_slot_it_touches():
    assert statuses(slots_for(bookings=[(mx(19, 30), mx(20, 30))])) == [A, B, B]


def test_a_blackout_blocks_the_slots_it_covers():
    assert statuses(slots_for(blackouts=[(mx(19), mx(21))])) == [A, K, K]


def test_a_blackout_covering_the_whole_day_blocks_everything():
    day_start = datetime(2026, 10, 14, tzinfo=MX).astimezone(UTC)
    day_end = datetime(2026, 10, 15, tzinfo=MX).astimezone(UTC)

    assert statuses(slots_for(blackouts=[(day_start, day_end)])) == [K, K, K]


def test_a_booking_inside_a_blackout_stays_visible_as_booked():
    slots = slots_for(blackouts=[(mx(18), mx(21))], bookings=[(mx(19), mx(20))])

    assert statuses(slots) == [K, B, K]


def test_a_booking_that_ends_when_the_court_opens_does_not_touch_the_first_slot():
    assert statuses(slots_for(bookings=[(mx(16), mx(18))])) == [A, A, A]


# --- the clock -------------------------------------------------------------------------------


def test_slots_that_already_started_are_past():
    assert statuses(slots_for(now=mx(19, 30))) == [P, P, A]


def test_a_slot_starting_exactly_now_can_still_be_booked():
    assert statuses(slots_for(now=mx(19))) == [P, A, A]


def test_a_past_slot_that_was_booked_still_reads_as_booked():
    assert statuses(slots_for(now=mx(20), bookings=[(mx(18), mx(19))])) == [B, P, A]


# --- daylight saving time --------------------------------------------------------------------


def test_spring_forward_day_has_one_real_hour_less():
    """2026-03-08 New York: 02:00 does not exist, so 01:00 to 04:00 local is only two hours."""
    slots = slots_for(day=date(2026, 3, 8), tz=NEW_YORK, window=(time(1), time(4)))

    assert [s.start for s in slots] == [
        datetime(2026, 3, 8, 6, tzinfo=UTC),  # 01:00 EST
        datetime(2026, 3, 8, 7, tzinfo=UTC),  # 03:00 EDT is 07:00 UTC; 02:00 EST never existed
    ]


def test_fall_back_day_has_one_real_hour_more():
    """2026-11-01 New York: 01:00 happens twice, so 01:00 to 04:00 local is four hours."""
    slots = slots_for(day=date(2026, 11, 1), tz=NEW_YORK, window=(time(1), time(4)))

    assert len(slots) == 4
    assert slots[0].start == datetime(2026, 11, 1, 5, tzinfo=UTC)  # first 01:00, still EDT


@pytest.mark.parametrize(
    ("tz", "expected_start"),
    [
        (ZoneInfo("Asia/Tokyo"), datetime(2026, 10, 14, 0, tzinfo=UTC)),  # UTC+9
        (ZoneInfo("UTC"), datetime(2026, 10, 14, 9, tzinfo=UTC)),
        (ZoneInfo("Pacific/Kiritimati"), datetime(2026, 10, 13, 19, tzinfo=UTC)),  # UTC+14
    ],
)
def test_the_same_local_hour_maps_to_different_utc_moments(tz, expected_start):
    slots = slots_for(tz=tz, window=(time(9), time(10)))

    assert slots[0].start == expected_start
