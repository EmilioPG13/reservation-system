"""Courts, opening hours, blackouts and the day grid, end to end over HTTP."""

import uuid
from datetime import UTC, datetime, time

import pytest
from httpx import AsyncClient
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Blackout, OpeningHours, Reservation, Resource, User
from app.services import auth as auth_service

# A Wednesday far in the future, so no slot is ever "past" whatever day the suite runs.
WEDNESDAY = "2030-06-12"
WEDNESDAY_WEEKDAY = 2
EVENING = {"open_time": "18:00:00", "close_time": "21:00:00"}


def utc(day: int, hour: int) -> datetime:
    return datetime(2030, 6, day, hour, tzinfo=UTC)


def during(start: datetime, end: datetime) -> Range[datetime]:
    return Range(start, end, bounds="[)")


async def make_court(
    session: AsyncSession, name: str = "Court 1", *, tz: str = "America/Mexico_City", **fields
) -> Resource:
    resource = Resource(name=name, timezone=tz, **fields)
    session.add(resource)
    await session.flush()
    return resource


async def open_on_wednesday(session: AsyncSession, court: Resource, open_: str, close: str):
    session.add(
        OpeningHours(
            resource_id=court.id,
            weekday=WEDNESDAY_WEEKDAY,
            open_time=time.fromisoformat(open_),
            close_time=time.fromisoformat(close),
        )
    )
    await session.flush()


# --- who may do what -----------------------------------------------------------------------

ADMIN_ROUTES = [
    ("GET", "/admin/resources"),
    ("POST", "/admin/resources"),
    ("GET", f"/admin/resources/{uuid.uuid4()}"),
    ("PATCH", f"/admin/resources/{uuid.uuid4()}"),
    ("PUT", f"/admin/resources/{uuid.uuid4()}/opening-hours"),
    ("GET", f"/admin/resources/{uuid.uuid4()}/blackouts"),
    ("POST", f"/admin/resources/{uuid.uuid4()}/blackouts"),
    ("DELETE", f"/admin/resources/{uuid.uuid4()}/blackouts/{uuid.uuid4()}"),
]


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
async def test_admin_routes_reject_anonymous_callers(api_client: AsyncClient, method, path):
    assert (await api_client.request(method, path)).status_code == 401


@pytest.mark.parametrize(("method", "path"), ADMIN_ROUTES)
async def test_admin_routes_reject_regular_users(
    api_client: AsyncClient, user_headers: dict, method, path
):
    response = await api_client.request(method, path, headers=user_headers)

    assert response.status_code == 403


@pytest.mark.parametrize("path", ["/resources", f"/availability?date={WEDNESDAY}"])
async def test_reading_courts_requires_login(api_client: AsyncClient, path):
    assert (await api_client.get(path)).status_code == 401


# --- creating and editing courts -----------------------------------------------------------


async def test_admin_creates_a_court_with_defaults(api_client: AsyncClient, admin_headers: dict):
    response = await api_client.post(
        "/admin/resources", json={"name": "Court 7"}, headers=admin_headers
    )

    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Court 7"
    assert body["timezone"] == "America/Mexico_City"
    assert body["slot_minutes"] == 60
    assert body["active"] is True
    assert body["opening_hours"] == []


@pytest.mark.parametrize(
    "payload",
    [
        {"name": ""},
        {"name": "x", "timezone": "Mars/Olympus_Mons"},
        {"name": "x", "timezone": "../etc/passwd"},
        {"name": "x", "slot_minutes": 0},
        {"name": "x", "slot_minutes": 24 * 60},
    ],
)
async def test_invalid_courts_are_rejected(api_client: AsyncClient, admin_headers: dict, payload):
    response = await api_client.post("/admin/resources", json=payload, headers=admin_headers)

    assert response.status_code == 422


async def test_patch_changes_only_the_fields_sent(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session, description="Glass walls")

    response = await api_client.patch(
        f"/admin/resources/{court.id}", json={"name": "Centre court"}, headers=admin_headers
    )

    assert response.status_code == 200
    assert response.json()["name"] == "Centre court"
    assert response.json()["description"] == "Glass walls"


async def test_patch_can_clear_the_description(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session, description="Glass walls")

    response = await api_client.patch(
        f"/admin/resources/{court.id}", json={"description": None}, headers=admin_headers
    )

    assert response.json()["description"] is None


@pytest.mark.parametrize("field", ["name", "timezone", "slot_minutes", "active"])
async def test_patch_refuses_null_for_required_fields(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession, field
):
    court = await make_court(session)

    response = await api_client.patch(
        f"/admin/resources/{court.id}", json={field: None}, headers=admin_headers
    )

    assert response.status_code == 422


async def test_unknown_court_is_a_404(api_client: AsyncClient, admin_headers: dict):
    response = await api_client.patch(
        f"/admin/resources/{uuid.uuid4()}", json={"name": "x"}, headers=admin_headers
    )

    assert response.status_code == 404


async def test_deactivated_courts_are_hidden_from_users_but_not_from_admins(
    api_client: AsyncClient, admin_headers: dict, user_headers: dict, session: AsyncSession
):
    await make_court(session, "Live")
    retired = await make_court(session, "Retired")
    await api_client.patch(
        f"/admin/resources/{retired.id}", json={"active": False}, headers=admin_headers
    )

    seen_by_user = await api_client.get("/resources", headers=user_headers)
    seen_by_admin = await api_client.get("/admin/resources", headers=admin_headers)

    assert [c["name"] for c in seen_by_user.json()] == ["Live"]
    assert [c["name"] for c in seen_by_admin.json()] == ["Live", "Retired"]


# --- opening hours -------------------------------------------------------------------------


async def test_opening_hours_replace_the_whole_week(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session)
    url = f"/admin/resources/{court.id}/opening-hours"
    weekdays = [{"weekday": d, **EVENING} for d in range(5)]

    first = await api_client.put(url, json={"hours": weekdays}, headers=admin_headers)
    second = await api_client.put(
        url,
        json={"hours": [{"weekday": 5, "open_time": "09:00:00", "close_time": "14:00:00"}]},
        headers=admin_headers,
    )

    assert [h["weekday"] for h in first.json()["opening_hours"]] == [0, 1, 2, 3, 4]
    assert second.json()["opening_hours"] == [
        {"weekday": 5, "open_time": "09:00:00", "close_time": "14:00:00"}
    ]


async def test_changing_the_window_of_an_existing_weekday_updates_it(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session)
    url = f"/admin/resources/{court.id}/opening-hours"
    await api_client.put(url, json={"hours": [{"weekday": 0, **EVENING}]}, headers=admin_headers)

    response = await api_client.put(
        url,
        json={"hours": [{"weekday": 0, "open_time": "08:00:00", "close_time": "12:00:00"}]},
        headers=admin_headers,
    )

    assert response.status_code == 200
    assert response.json()["opening_hours"][0]["open_time"] == "08:00:00"


async def test_an_empty_list_closes_the_court_every_day(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session)
    url = f"/admin/resources/{court.id}/opening-hours"
    await api_client.put(url, json={"hours": [{"weekday": 0, **EVENING}]}, headers=admin_headers)

    response = await api_client.put(url, json={"hours": []}, headers=admin_headers)

    assert response.json()["opening_hours"] == []


@pytest.mark.parametrize(
    "hours",
    [
        [{"weekday": 7, **EVENING}],
        [{"weekday": -1, **EVENING}],
        [{"weekday": 0, "open_time": "21:00:00", "close_time": "18:00:00"}],
        [{"weekday": 0, "open_time": "18:00:00", "close_time": "18:00:00"}],
        [{"weekday": 0, "open_time": "18:00:00+02:00", "close_time": "21:00:00+02:00"}],
        [{"weekday": 1, **EVENING}, {"weekday": 1, **EVENING}],
    ],
    ids=[
        "weekday-above-6",
        "negative-weekday",
        "closes-before-opening",
        "zero-length-window",
        "time-with-offset",
        "weekday-twice",
    ],
)
async def test_invalid_opening_hours_are_rejected(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession, hours
):
    court = await make_court(session)

    response = await api_client.put(
        f"/admin/resources/{court.id}/opening-hours", json={"hours": hours}, headers=admin_headers
    )

    assert response.status_code == 422


# --- blackouts -----------------------------------------------------------------------------


def blackout_body(**overrides):
    return {
        "starts_at": "2030-06-12T00:00:00Z",
        "ends_at": "2030-06-12T06:00:00Z",
        "reason": "Resurfacing",
        **overrides,
    }


async def test_blackouts_can_be_created_listed_and_deleted(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session)
    url = f"/admin/resources/{court.id}/blackouts"

    created = await api_client.post(url, json=blackout_body(), headers=admin_headers)
    listed = await api_client.get(url, headers=admin_headers)
    deleted = await api_client.delete(f"{url}/{created.json()['id']}", headers=admin_headers)
    after = await api_client.get(url, headers=admin_headers)

    assert created.status_code == 201
    assert created.json()["reason"] == "Resurfacing"
    assert [b["id"] for b in listed.json()] == [created.json()["id"]]
    assert deleted.status_code == 204
    assert after.json() == []


async def test_blackout_times_survive_the_round_trip_as_the_same_moment(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session)

    response = await api_client.post(
        f"/admin/resources/{court.id}/blackouts",
        json=blackout_body(starts_at="2030-06-11T18:00:00-06:00", ends_at="2030-06-12T06:00:00Z"),
        headers=admin_headers,
    )

    returned = datetime.fromisoformat(response.json()["starts_at"])
    assert returned == datetime(2030, 6, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "overrides",
    [
        {"ends_at": "2030-06-11T23:00:00Z"},
        {"ends_at": "2030-06-12T00:00:00Z"},
        {"starts_at": "2030-06-12T00:00:00"},
    ],
    ids=["ends-before-start", "empty-window", "no-time-zone"],
)
async def test_invalid_blackouts_are_rejected(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession, overrides
):
    court = await make_court(session)

    response = await api_client.post(
        f"/admin/resources/{court.id}/blackouts",
        json=blackout_body(**overrides),
        headers=admin_headers,
    )

    assert response.status_code == 422


async def test_a_blackout_cannot_be_deleted_through_another_court(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    mine = await make_court(session, "Mine")
    other = await make_court(session, "Other")
    blackout = Blackout(resource_id=mine.id, during=during(utc(12, 0), utc(12, 6)))
    session.add(blackout)
    await session.flush()

    response = await api_client.delete(
        f"/admin/resources/{other.id}/blackouts/{blackout.id}", headers=admin_headers
    )

    assert response.status_code == 404


async def test_blackouts_of_an_unknown_court_are_a_404(
    api_client: AsyncClient, admin_headers: dict
):
    response = await api_client.post(
        f"/admin/resources/{uuid.uuid4()}/blackouts", json=blackout_body(), headers=admin_headers
    )

    assert response.status_code == 404


# --- the day grid --------------------------------------------------------------------------


async def grid(client: AsyncClient, headers: dict, day: str = WEDNESDAY) -> dict:
    response = await client.get(f"/availability?date={day}", headers=headers)
    assert response.status_code == 200
    return response.json()


def statuses(court: dict) -> list[str]:
    return [s["status"] for s in court["slots"]]


async def test_the_grid_has_every_active_court_in_one_response(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession
):
    for name in ("Court 2", "Court 1", "Court 3"):
        court = await make_court(session, name)
        await open_on_wednesday(session, court, "18:00", "21:00")
    await make_court(session, "Closed down", active=False)

    body = await grid(api_client, user_headers)

    assert body["date"] == WEDNESDAY
    assert [c["name"] for c in body["courts"]] == ["Court 1", "Court 2", "Court 3"]
    assert all(statuses(c) == ["available"] * 3 for c in body["courts"])


async def test_slots_come_back_as_utc_moments(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession
):
    court = await make_court(session)
    await open_on_wednesday(session, court, "18:00", "19:00")

    slot = (await grid(api_client, user_headers))["courts"][0]["slots"][0]

    assert datetime.fromisoformat(slot["start"]) == utc(13, 0)  # 18:00 in UTC-6
    assert datetime.fromisoformat(slot["end"]) == utc(13, 1)


async def test_a_court_closed_that_day_appears_with_no_slots(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession
):
    await make_court(session)

    body = await grid(api_client, user_headers)

    assert body["courts"][0]["slots"] == []


async def test_confirmed_reservations_show_as_booked_and_cancelled_ones_do_not(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession, user: User
):
    court = await make_court(session)
    await open_on_wednesday(session, court, "18:00", "21:00")
    session.add_all(
        [
            Reservation(  # 19:00 local
                resource_id=court.id, user_id=user.id, during=during(utc(13, 1), utc(13, 2))
            ),
            Reservation(  # 20:00 local, cancelled: the slot is free again
                resource_id=court.id,
                user_id=user.id,
                during=during(utc(13, 2), utc(13, 3)),
                status="cancelled",
            ),
        ]
    )
    await session.flush()

    body = await grid(api_client, user_headers)

    assert statuses(body["courts"][0]) == ["available", "booked", "available"]


async def test_blackouts_show_as_blocked(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession
):
    court = await make_court(session)
    await open_on_wednesday(session, court, "18:00", "21:00")
    session.add(Blackout(resource_id=court.id, during=during(utc(13, 0), utc(13, 2))))
    await session.flush()

    body = await grid(api_client, user_headers)

    assert statuses(body["courts"][0]) == ["blocked", "blocked", "available"]


async def test_a_reservation_on_one_court_does_not_touch_another(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession, user: User
):
    busy = await make_court(session, "Busy")
    quiet = await make_court(session, "Quiet")
    for court in (busy, quiet):
        await open_on_wednesday(session, court, "18:00", "19:00")
    session.add(
        Reservation(resource_id=busy.id, user_id=user.id, during=during(utc(13, 0), utc(13, 1)))
    )
    await session.flush()

    courts = {c["name"]: c for c in (await grid(api_client, user_headers))["courts"]}

    assert statuses(courts["Busy"]) == ["booked"]
    assert statuses(courts["Quiet"]) == ["available"]


async def test_each_court_reads_the_date_in_its_own_time_zone(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession
):
    mexico = await make_court(session, "Mexico")
    tokyo = await make_court(session, "Tokyo", tz="Asia/Tokyo")
    await open_on_wednesday(session, mexico, "09:00", "10:00")
    await open_on_wednesday(session, tokyo, "09:00", "10:00")

    courts = {c["name"]: c for c in (await grid(api_client, user_headers))["courts"]}

    assert datetime.fromisoformat(courts["Mexico"]["slots"][0]["start"]) == utc(12, 15)
    assert datetime.fromisoformat(courts["Tokyo"]["slots"][0]["start"]) == utc(12, 0)


async def test_a_past_date_has_only_past_slots(
    api_client: AsyncClient, user_headers: dict, session: AsyncSession
):
    court = await make_court(session)
    await open_on_wednesday(session, court, "18:00", "21:00")

    body = await grid(api_client, user_headers, day="2020-06-10")  # also a Wednesday

    assert statuses(body["courts"][0]) == ["past"] * 3


@pytest.mark.parametrize("query", ["", "?date=not-a-date", "?date=2030-02-30"])
async def test_the_grid_needs_a_valid_date(api_client: AsyncClient, user_headers: dict, query):
    response = await api_client.get(f"/availability{query}", headers=user_headers)

    assert response.status_code == 422


async def test_no_courts_means_an_empty_grid(api_client: AsyncClient, user_headers: dict):
    assert (await grid(api_client, user_headers))["courts"] == []


# --- the create-admin command's service --------------------------------------------------


async def test_create_admin_makes_an_admin_who_can_use_admin_routes(
    api_client: AsyncClient, session: AsyncSession
):
    admin = await auth_service.create_admin(
        session, email="Owner@Example.com", password="correct horse battery", name="Owner"
    )
    login = await api_client.post(
        "/auth/login", data={"username": "owner@example.com", "password": "correct horse battery"}
    )

    response = await api_client.get(
        "/admin/resources",
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )

    assert admin.role == "admin"
    assert response.status_code == 200


# --- remaining admin paths -----------------------------------------------------------------


async def test_admin_reads_one_court(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session, "Centre")

    response = await api_client.get(f"/admin/resources/{court.id}", headers=admin_headers)

    assert response.status_code == 200
    assert response.json()["name"] == "Centre"


@pytest.mark.parametrize(
    ("method", "suffix", "body"),
    [
        ("GET", "", None),
        ("PUT", "/opening-hours", {"hours": []}),
        ("GET", "/blackouts", None),
    ],
)
async def test_admin_routes_on_an_unknown_court_are_404(
    api_client: AsyncClient, admin_headers: dict, method, suffix, body
):
    response = await api_client.request(
        method, f"/admin/resources/{uuid.uuid4()}{suffix}", json=body, headers=admin_headers
    )

    assert response.status_code == 404


async def test_deleting_an_unknown_blackout_is_a_404(
    api_client: AsyncClient, admin_headers: dict, session: AsyncSession
):
    court = await make_court(session)

    response = await api_client.delete(
        f"/admin/resources/{court.id}/blackouts/{uuid.uuid4()}", headers=admin_headers
    )

    assert response.status_code == 404
