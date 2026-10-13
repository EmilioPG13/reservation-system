"""Booking, cancelling, "my reservations" and the admin day view, end to end over HTTP."""

import uuid
from datetime import UTC, datetime, time, timedelta

import pytest
from httpx import AsyncClient, Response
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models import Blackout, OpeningHours, Reservation, Resource, User

# Far in the future so no slot is ever "past" and no reservation ever "ended", whatever day the
# suite runs. Courts here are in UTC and open 08:00-22:00 every day, in one-hour slots.
DAY = datetime(2030, 6, 12, tzinfo=UTC)


def at(hour: int, day: datetime = DAY) -> datetime:
    return day.replace(hour=hour)


def hours_from_now(hours: float) -> datetime:
    return datetime.now(UTC) + timedelta(hours=hours)


def during(start: datetime, hours: int = 1) -> Range[datetime]:
    return Range(start, start + timedelta(hours=hours), bounds="[)")


@pytest.fixture
async def venue(session: AsyncSession) -> uuid.UUID:
    """The id of a UTC court open every day from 08:00 to 22:00."""
    court = Resource(
        name="Court 1",
        timezone="UTC",
        opening_hours=[
            OpeningHours(weekday=d, open_time=time(8), close_time=time(22)) for d in range(7)
        ],
    )
    session.add(court)
    await session.flush()
    return court.id


@pytest.fixture
async def other_user(session: AsyncSession) -> User:
    u = User(email="rival@example.com", password_hash="x", name="Rival")
    session.add(u)
    await session.flush()
    return u


@pytest.fixture
def other_headers(other_user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(str(other_user.id))}"}


async def reserve(
    session: AsyncSession,
    court_id: uuid.UUID,
    user_id: uuid.UUID,
    start: datetime,
    *,
    status: str = "confirmed",
) -> Reservation:
    """Insert a reservation directly, to set up states the API would refuse to create."""
    reservation = Reservation(
        resource_id=court_id, user_id=user_id, during=during(start), status=status
    )
    session.add(reservation)
    await session.flush()
    return reservation


async def book(
    client: AsyncClient, headers: dict, court_id: uuid.UUID, start: datetime
) -> Response:
    return await client.post(
        "/reservations",
        json={"resource_id": str(court_id), "starts_at": start.isoformat()},
        headers=headers,
    )


# --- who may do what -----------------------------------------------------------------------

USER_ROUTES = [
    ("POST", "/reservations"),
    ("GET", "/reservations"),
    ("POST", f"/reservations/{uuid.uuid4()}/cancel"),
]
ADMIN_ROUTES = [
    ("GET", "/admin/reservations?date=2030-06-12"),
    ("POST", f"/admin/reservations/{uuid.uuid4()}/cancel"),
]


@pytest.mark.parametrize(("method", "path"), USER_ROUTES + ADMIN_ROUTES)
async def test_routes_reject_anonymous_callers(api_client: AsyncClient, method, path):
    assert (await api_client.request(method, path)).status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
async def test_admin_routes_reject_regular_users(
    api_client: AsyncClient, user_headers: dict, method, path
):
    assert (await api_client.request(method, path, headers=user_headers)).status_code == 403


# --- booking -------------------------------------------------------------------------------


async def test_booking_a_slot_returns_the_reservation(
    api_client: AsyncClient, user_headers: dict, user: User, venue: uuid.UUID
):
    response = await book(api_client, user_headers, venue, at(10))

    assert response.status_code == 201
    body = response.json()
    assert body["resource_id"] == str(venue)
    assert datetime.fromisoformat(body["starts_at"]) == at(10)
    assert datetime.fromisoformat(body["ends_at"]) == at(11)
    assert body["status"] == "confirmed"
    assert body["cancelled_at"] is None


async def test_a_taken_slot_is_a_409_for_everyone_else(
    api_client: AsyncClient, user_headers: dict, other_headers: dict, venue: uuid.UUID
):
    assert (await book(api_client, user_headers, venue, at(10))).status_code == 201

    rival = await book(api_client, other_headers, venue, at(10))
    same_user = await book(api_client, user_headers, venue, at(10))

    assert rival.status_code == 409
    assert rival.json()["detail"] == "That slot was just taken"
    assert same_user.status_code == 409


async def test_back_to_back_slots_do_not_conflict(
    api_client: AsyncClient, user_headers: dict, other_headers: dict, venue: uuid.UUID
):
    assert (await book(api_client, user_headers, venue, at(10))).status_code == 201

    assert (await book(api_client, other_headers, venue, at(11))).status_code == 201
    assert (await book(api_client, other_headers, venue, at(9))).status_code == 201


async def test_a_cancelled_slot_can_be_booked_again(
    api_client: AsyncClient, user_headers: dict, other_headers: dict, venue: uuid.UUID
):
    first = (await book(api_client, user_headers, venue, at(10))).json()
    cancel = await api_client.post(f"/reservations/{first['id']}/cancel", headers=user_headers)
    assert cancel.status_code == 200

    assert (await book(api_client, other_headers, venue, at(10))).status_code == 201


@pytest.mark.parametrize(
    "start",
    [
        datetime(2030, 6, 12, 10, 30, tzinfo=UTC),  # between slot boundaries
        datetime(2030, 6, 12, 10, 0, 1, tzinfo=UTC),  # a second off
        datetime(2030, 6, 12, 7, tzinfo=UTC),  # before opening
        datetime(2030, 6, 12, 22, tzinfo=UTC),  # at closing: no slot starts there
    ],
)
async def test_only_the_start_of_a_real_slot_can_be_booked(
    api_client: AsyncClient, user_headers: dict, venue: uuid.UUID, start: datetime
):
    response = await book(api_client, user_headers, venue, start)

    assert response.status_code == 422


async def test_a_day_the_court_is_closed_cannot_be_booked(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession
):
    closed = Resource(name="Closed", timezone="UTC", opening_hours=[])
    session.add(closed)
    await session.flush()

    assert (await book(api_client, user_headers, closed.id, at(10))).status_code == 422


async def test_a_slot_that_already_started_cannot_be_booked(
    api_client: AsyncClient, user_headers: dict, venue: uuid.UUID
):
    yesterday = (datetime.now(UTC) - timedelta(days=1)).replace(
        hour=10, minute=0, second=0, microsecond=0
    )

    response = await book(api_client, user_headers, venue, yesterday)

    assert response.status_code == 422
    assert response.json()["detail"] == "That slot has already started"


async def test_a_blocked_slot_cannot_be_booked(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession, venue: uuid.UUID
):
    session.add(Blackout(resource_id=venue, during=during(at(10), hours=2)))
    await session.flush()

    assert (await book(api_client, user_headers, venue, at(10))).status_code == 422
    assert (await book(api_client, user_headers, venue, at(11))).status_code == 422
    assert (await book(api_client, user_headers, venue, at(12))).status_code == 201


async def test_an_unknown_or_inactive_court_is_a_404(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession, venue: uuid.UUID
):
    retired = await session.get(Resource, venue, populate_existing=True)
    retired.active = False
    await session.flush()

    assert (await book(api_client, user_headers, uuid.uuid4(), at(10))).status_code == 404
    assert (await book(api_client, user_headers, venue, at(10))).status_code == 404


async def test_a_start_without_a_time_zone_is_rejected(
    api_client: AsyncClient, user_headers: dict, venue: uuid.UUID
):
    response = await api_client.post(
        "/reservations",
        json={"resource_id": str(venue), "starts_at": "2030-06-12T10:00:00"},
        headers=user_headers,
    )

    assert response.status_code == 422


# --- the limit of active reservations ------------------------------------------------------


async def test_a_user_cannot_hold_more_than_the_limit(
    api_client: AsyncClient, user_headers: dict, venue: uuid.UUID
):
    limit = settings.max_active_reservations
    for hour in range(10, 10 + limit):
        assert (await book(api_client, user_headers, venue, at(hour))).status_code == 201

    over = await book(api_client, user_headers, venue, at(10 + limit))

    assert over.status_code == 422
    assert str(limit) in over.json()["detail"]


async def test_cancelled_and_finished_reservations_do_not_count_toward_the_limit(
    api_client: AsyncClient,
    user_headers: dict,
    session: AsyncSession,
    user: User,
    venue: uuid.UUID,
):
    user_id = user.id
    for hour in range(settings.max_active_reservations):
        await reserve(session, venue, user_id, at(10 + hour), status="cancelled")
    await reserve(session, venue, user_id, hours_from_now(-48))  # already over

    assert (await book(api_client, user_headers, venue, at(18))).status_code == 201


async def test_the_limit_is_per_user(
    api_client: AsyncClient,
    user_headers: dict,
    other_headers: dict,
    venue: uuid.UUID,
):
    for hour in range(settings.max_active_reservations):
        await book(api_client, user_headers, venue, at(10 + hour))

    assert (await book(api_client, other_headers, venue, at(18))).status_code == 201


# --- my reservations -----------------------------------------------------------------------


async def test_my_reservations_lists_only_mine_latest_first(
    api_client: AsyncClient,
    user_headers: dict,
    session: AsyncSession,
    user: User,
    other_user: User,
    venue: uuid.UUID,
):
    user_id, other_id = user.id, other_user.id
    for hour in (10, 12, 11):
        await reserve(session, venue, user_id, at(hour))
    await reserve(session, venue, other_id, at(15))

    response = await api_client.get("/reservations", headers=user_headers)

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 3
    starts = [datetime.fromisoformat(r["starts_at"]) for r in body["items"]]
    assert starts == [at(12), at(11), at(10)]


async def test_my_reservations_are_paginated(
    api_client: AsyncClient,
    user_headers: dict,
    session: AsyncSession,
    user: User,
    venue: uuid.UUID,
):
    user_id = user.id
    for hour in range(10, 15):
        await reserve(session, venue, user_id, at(hour))

    page = (await api_client.get("/reservations?limit=2&offset=2", headers=user_headers)).json()

    assert page["total"] == 5
    assert (page["limit"], page["offset"]) == (2, 2)
    starts = [datetime.fromisoformat(r["starts_at"]) for r in page["items"]]
    assert starts == [at(12), at(11)]


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1"])
async def test_pagination_bounds_are_enforced(
    api_client: AsyncClient, user_headers: dict, query: str
):
    assert (await api_client.get(f"/reservations?{query}", headers=user_headers)).status_code == 422


# --- cancelling ----------------------------------------------------------------------------


async def test_cancelling_frees_the_slot_in_the_grid(
    api_client: AsyncClient, user_headers: dict, venue: uuid.UUID
):
    reservation = (await book(api_client, user_headers, venue, at(10))).json()

    response = await api_client.post(
        f"/reservations/{reservation['id']}/cancel", headers=user_headers
    )

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancelled_at"] is not None
    grid = (await api_client.get("/availability?date=2030-06-12", headers=user_headers)).json()
    slot = next(s for s in grid["courts"][0]["slots"] if s["start"].startswith("2030-06-12T10"))
    assert slot["status"] == "available"


async def test_a_reservation_cannot_be_cancelled_twice(
    api_client: AsyncClient, user_headers: dict, venue: uuid.UUID
):
    reservation = (await book(api_client, user_headers, venue, at(10))).json()
    url = f"/reservations/{reservation['id']}/cancel"
    await api_client.post(url, headers=user_headers)

    assert (await api_client.post(url, headers=user_headers)).status_code == 409


async def test_someone_elses_reservation_looks_missing(
    api_client: AsyncClient, user_headers: dict, other_headers: dict, venue: uuid.UUID
):
    reservation = (await book(api_client, user_headers, venue, at(10))).json()

    response = await api_client.post(
        f"/reservations/{reservation['id']}/cancel", headers=other_headers
    )

    assert response.status_code == 404


async def test_cancelling_inside_the_window_is_refused(
    api_client: AsyncClient,
    user_headers: dict,
    session: AsyncSession,
    user: User,
    venue: uuid.UUID,
):
    soon = await reserve(
        session, venue, user.id, hours_from_now(settings.cancellation_window_hours - 1)
    )

    response = await api_client.post(f"/reservations/{soon.id}/cancel", headers=user_headers)

    assert response.status_code == 422
    assert str(settings.cancellation_window_hours) in response.json()["detail"]


async def test_cancelling_outside_the_window_works(
    api_client: AsyncClient,
    user_headers: dict,
    session: AsyncSession,
    user: User,
    venue: uuid.UUID,
):
    later = await reserve(
        session, venue, user.id, hours_from_now(settings.cancellation_window_hours + 1)
    )

    response = await api_client.post(f"/reservations/{later.id}/cancel", headers=user_headers)

    assert response.status_code == 200


async def test_cancelling_an_unknown_reservation_is_a_404(
    api_client: AsyncClient, user_headers: dict
):
    response = await api_client.post(f"/reservations/{uuid.uuid4()}/cancel", headers=user_headers)

    assert response.status_code == 404


# --- admin ---------------------------------------------------------------------------------


async def test_an_admin_can_cancel_anyones_reservation_even_inside_the_window(
    api_client: AsyncClient,
    admin_headers: dict,
    session: AsyncSession,
    user: User,
    venue: uuid.UUID,
):
    soon = await reserve(session, venue, user.id, hours_from_now(1))
    url = f"/admin/reservations/{soon.id}/cancel"

    first = await api_client.post(url, headers=admin_headers)
    again = await api_client.post(url, headers=admin_headers)

    assert first.status_code == 200
    assert first.json()["status"] == "cancelled"
    assert again.status_code == 409


async def test_an_admin_cancelling_an_unknown_reservation_gets_a_404(
    api_client: AsyncClient, admin_headers: dict
):
    response = await api_client.post(
        f"/admin/reservations/{uuid.uuid4()}/cancel", headers=admin_headers
    )

    assert response.status_code == 404


async def test_an_admin_cancelling_frees_a_reservation_left_under_a_blackout(
    api_client: AsyncClient,
    admin_headers: dict,
    user_headers: dict,
    session: AsyncSession,
    venue: uuid.UUID,
):
    booked = (await book(api_client, user_headers, venue, at(10))).json()
    session.add(Blackout(resource_id=venue, during=during(at(9), hours=4)))
    await session.flush()

    await api_client.post(f"/admin/reservations/{booked['id']}/cancel", headers=admin_headers)

    grid = (await api_client.get("/availability?date=2030-06-12", headers=admin_headers)).json()
    slot = next(s for s in grid["courts"][0]["slots"] if s["start"].startswith("2030-06-12T10"))
    assert slot["status"] == "blocked"  # the blackout now applies: nothing is hiding under it


async def test_the_admin_day_view_says_who_booked(
    api_client: AsyncClient,
    admin_headers: dict,
    session: AsyncSession,
    user: User,
):
    mexico = Resource(name="Mexico court", timezone="America/Mexico_City")
    session.add(mexico)
    await session.flush()
    # 21:00 local on the 12th is already the 13th in UTC.
    late = datetime(2030, 6, 13, 3, tzinfo=UTC)
    await reserve(session, mexico.id, user.id, late)
    await reserve(session, mexico.id, user.id, late + timedelta(hours=24))  # the 13th, local
    await reserve(session, mexico.id, user.id, late + timedelta(hours=1), status="cancelled")

    rows = (
        await api_client.get("/admin/reservations?date=2030-06-12", headers=admin_headers)
    ).json()

    assert len(rows) == 1
    row = rows[0]
    assert datetime.fromisoformat(row["starts_at"]) == late
    assert row["resource_name"] == "Mexico court"
    assert (row["user_name"], row["user_email"]) == (user.name, user.email)


# --- "mine" in the grid --------------------------------------------------------------------


async def test_the_grid_marks_only_my_own_bookings_as_mine(
    api_client: AsyncClient, user_headers: dict, other_headers: dict, venue: uuid.UUID
):
    await book(api_client, user_headers, venue, at(10))
    await book(api_client, other_headers, venue, at(11))

    async def slots_for(headers: dict) -> dict[int, dict]:
        grid = (await api_client.get("/availability?date=2030-06-12", headers=headers)).json()
        return {datetime.fromisoformat(s["start"]).hour: s for s in grid["courts"][0]["slots"]}

    mine = await slots_for(user_headers)
    theirs = await slots_for(other_headers)

    assert (mine[10]["status"], mine[10]["mine"]) == ("booked", True)
    assert (mine[11]["status"], mine[11]["mine"]) == ("booked", False)
    assert (theirs[10]["status"], theirs[10]["mine"]) == ("booked", False)
    assert (theirs[11]["status"], theirs[11]["mine"]) == ("booked", True)
    assert mine[12]["mine"] is False  # a free slot is never mine


async def test_a_cancelled_booking_is_no_longer_mine(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession, user: User, venue
):
    await reserve(session, venue, user.id, at(10), status="cancelled")

    grid = (await api_client.get("/availability?date=2030-06-12", headers=user_headers)).json()

    assert not any(s["mine"] for s in grid["courts"][0]["slots"])


async def test_the_booking_survives_in_the_database_as_a_half_open_range(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession, venue: uuid.UUID
):
    await book(api_client, user_headers, venue, at(10))

    stored = await session.scalar(
        select(Reservation.during).where(Reservation.resource_id == venue)
    )

    assert (stored.lower, stored.upper, stored.bounds) == (at(10), at(11), "[)")
