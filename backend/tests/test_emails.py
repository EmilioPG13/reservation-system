"""The confirmation and cancellation emails, and that no mail problem ever breaks a reservation."""

import logging
import uuid
from datetime import UTC, datetime, time, timedelta
from email.message import EmailMessage
from zoneinfo import ZoneInfo

import httpx
import pytest
from httpx import AsyncClient
from pydantic import SecretStr
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import OpeningHours, Reservation, Resource, User
from app.services import mailer
from app.services.notifications import Notice, compose

# The real transport, kept before the autouse `outbox` fixture replaces it in each test.
real_send = mailer.send

MEXICO = ZoneInfo("America/Mexico_City")  # UTC-6 all year since 2022
# 18:00 at the court is 00:00 UTC of the next day: the email must say the court's time.
EVENING = datetime(2030, 6, 12, 18, tzinfo=MEXICO)


@pytest.fixture
async def venue(session: AsyncSession) -> uuid.UUID:
    court = Resource(
        name="Court Azul",
        timezone="America/Mexico_City",
        opening_hours=[
            OpeningHours(weekday=d, open_time=time(8), close_time=time(22)) for d in range(7)
        ],
    )
    session.add(court)
    await session.flush()
    return court.id


async def book(client: AsyncClient, headers: dict, court_id: uuid.UUID, start: datetime):
    return await client.post(
        "/reservations",
        json={"resource_id": str(court_id), "starts_at": start.isoformat()},
        headers=headers,
    )


async def reservation_of(
    session: AsyncSession, court_id: uuid.UUID, user: User, start: datetime
) -> Reservation:
    reservation = Reservation(
        resource_id=court_id,
        user_id=user.id,
        during=Range(start, start + timedelta(hours=1), bounds="[)"),
    )
    session.add(reservation)
    await session.flush()
    return reservation


def text_of(message: EmailMessage) -> str:
    return message.get_content()


# --- confirmation ----------------------------------------------------------------------------


async def test_booking_sends_a_confirmation_in_the_courts_time(
    api_client: AsyncClient,
    user_headers: dict,
    user: User,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
):
    assert (await book(api_client, user_headers, venue, EVENING)).status_code == 201

    [message] = outbox
    assert message["To"].addresses[0].addr_spec == user.email
    assert message["To"].addresses[0].display_name == user.name
    assert message["Subject"] == "Booking confirmed: Court Azul, Wednesday, June 12, 2030 at 18:00"
    body = text_of(message)
    assert f"Hi {user.name}," in body
    assert "Time: 18:00 to 19:00 (CST)" in body


async def test_a_taken_slot_sends_nothing(
    api_client: AsyncClient,
    user_headers: dict,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
):
    await book(api_client, user_headers, venue, EVENING)
    outbox.clear()

    assert (await book(api_client, user_headers, venue, EVENING)).status_code == 409
    assert outbox == []


async def test_a_booking_the_rules_refuse_sends_nothing(
    api_client: AsyncClient,
    user_headers: dict,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
):
    closed = EVENING.replace(hour=3)

    assert (await book(api_client, user_headers, venue, closed)).status_code == 422
    assert outbox == []


# --- cancellation ----------------------------------------------------------------------------


async def test_cancelling_your_own_reservation_sends_a_cancellation(
    api_client: AsyncClient,
    session: AsyncSession,
    user_headers: dict,
    user: User,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
):
    reservation = await reservation_of(session, venue, user, EVENING)

    response = await api_client.post(f"/reservations/{reservation.id}/cancel", headers=user_headers)

    assert response.status_code == 200
    [message] = outbox
    assert message["To"].addresses[0].addr_spec == user.email
    assert message["Subject"].startswith("Booking cancelled: Court Azul")
    assert "You cancelled this booking." in text_of(message)


async def test_a_refused_cancellation_sends_nothing(
    api_client: AsyncClient,
    session: AsyncSession,
    user_headers: dict,
    user: User,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
):
    soon = datetime.now(UTC) + timedelta(hours=2)
    reservation = await reservation_of(session, venue, user, soon)

    response = await api_client.post(f"/reservations/{reservation.id}/cancel", headers=user_headers)

    assert response.status_code == 422
    assert outbox == []


async def test_an_admin_cancelling_tells_the_user_not_the_admin(
    api_client: AsyncClient,
    session: AsyncSession,
    admin_headers: dict,
    user: User,
    venue: uuid.UUID,
    outbox: list[EmailMessage],
):
    reservation = await reservation_of(session, venue, user, EVENING)

    response = await api_client.post(
        f"/admin/reservations/{reservation.id}/cancel", headers=admin_headers
    )

    assert response.status_code == 200
    [message] = outbox
    assert message["To"].addresses[0].addr_spec == user.email
    assert message["Subject"].startswith("Your booking was cancelled by the court: Court Azul")
    assert "maintenance" in text_of(message)


# --- when the mail does not work -------------------------------------------------------------


@pytest.fixture
def mail_server_down(monkeypatch: pytest.MonkeyPatch) -> None:
    async def refuse(message: EmailMessage) -> None:
        raise ConnectionRefusedError("SMTP server is down")

    monkeypatch.setattr(mailer, "send", refuse)


@pytest.mark.usefixtures("mail_server_down")
async def test_a_mail_server_that_is_down_does_not_undo_a_booking(
    api_client: AsyncClient,
    user_headers: dict,
    venue: uuid.UUID,
    caplog: pytest.LogCaptureFixture,
):
    with caplog.at_level(logging.ERROR, logger=mailer.logger.name):
        response = await book(api_client, user_headers, venue, EVENING)

    assert response.status_code == 201
    mine = await api_client.get("/reservations", headers=user_headers)
    assert mine.json()["total"] == 1
    assert "Could not send" in caplog.text


@pytest.mark.usefixtures("mail_server_down")
async def test_a_mail_server_that_is_down_does_not_undo_a_cancellation(
    api_client: AsyncClient,
    session: AsyncSession,
    user_headers: dict,
    user: User,
    venue: uuid.UUID,
):
    reservation = await reservation_of(session, venue, user, EVENING)

    response = await api_client.post(f"/reservations/{reservation.id}/cancel", headers=user_headers)

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


# --- the message itself ----------------------------------------------------------------------


def test_a_name_with_line_breaks_cannot_add_headers():
    start = datetime(2030, 6, 12, 18, tzinfo=MEXICO)
    reservation = Reservation(
        id=uuid.uuid4(), during=Range(start, start + timedelta(hours=1), bounds="[)")
    )
    court = Resource(name="Court\nBcc: spy@example.com", timezone="America/Mexico_City")
    user = User(email="player@example.com", name="Eve\nBcc: spy@example.com")

    message = compose(Notice.REMINDER, reservation, court, user)

    assert message["Bcc"] is None
    assert "\n" not in message["Subject"]


# --- the real SMTP transport -----------------------------------------------------------------

MAILPIT_API = "http://localhost:8025/api/v1/messages"


async def test_the_smtp_transport_delivers_to_mailpit(user: User):
    """Needs `docker compose up mailpit`; skipped when nothing answers on its port."""
    async with httpx.AsyncClient() as http:
        try:
            await http.delete(MAILPIT_API)
        except httpx.TransportError:
            pytest.skip("Mailpit is not running")

        start = datetime(2030, 6, 12, 18, tzinfo=MEXICO)
        reservation = Reservation(
            id=uuid.uuid4(), during=Range(start, start + timedelta(hours=1), bounds="[)")
        )
        court = Resource(name="Court Azul", timezone="America/Mexico_City")
        await real_send(compose(Notice.CONFIRMED, reservation, court, user))

        inbox = (await http.get(MAILPIT_API)).json()["messages"]

    assert [m["To"][0]["Address"] for m in inbox] == [user.email]
    assert inbox[0]["Subject"].startswith("Booking confirmed: Court Azul")


async def test_the_smtp_login_and_starttls_reach_the_transport(
    monkeypatch: pytest.MonkeyPatch,
):
    seen: dict = {}

    async def fake_send(message, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(mailer.aiosmtplib, "send", fake_send)
    monkeypatch.setattr(settings, "smtp_username", "apikey")
    monkeypatch.setattr(settings, "smtp_password", SecretStr("s3cret"))
    monkeypatch.setattr(settings, "smtp_start_tls", True)

    await real_send(EmailMessage())

    assert (seen["username"], seen["password"], seen["start_tls"]) == ("apikey", "s3cret", True)


async def test_without_credentials_the_transport_is_told_none(monkeypatch: pytest.MonkeyPatch):
    seen: dict = {}

    async def fake_send(message, **kwargs):
        seen.update(kwargs)

    monkeypatch.setattr(mailer.aiosmtplib, "send", fake_send)

    await real_send(EmailMessage())

    assert (seen["username"], seen["password"], seen["start_tls"]) == (None, None, False)
