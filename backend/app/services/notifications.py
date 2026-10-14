"""The emails about a reservation: what they say, in the court's own time."""

import logging
from email.headerregistry import Address
from email.message import EmailMessage
from enum import StrEnum
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Reservation, Resource, User

logger = logging.getLogger(__name__)


class Notice(StrEnum):
    CONFIRMED = "confirmed"
    CANCELLED = "cancelled"  # the user cancelled it
    CANCELLED_BY_COURT = "cancelled_by_court"  # an admin cancelled it, e.g. after a blackout
    REMINDER = "reminder"


def _one_line(text: str) -> str:
    """Header values cannot hold line breaks (and a name with one would be an injection)."""
    return " ".join(text.split())


def compose(
    notice: Notice, reservation: Reservation, resource: Resource, user: User
) -> EmailMessage:
    tz = ZoneInfo(resource.timezone)
    start = reservation.during.lower.astimezone(tz)
    end = reservation.during.upper.astimezone(tz)
    court = _one_line(resource.name)
    when = f"{start:%A}, {start:%B} {start.day}, {start:%Y} at {start:%H:%M}"
    details = (
        f"Court: {court}\n"
        f"Date: {start:%A}, {start:%B} {start.day}, {start:%Y}\n"
        f"Time: {start:%H:%M} to {end:%H:%M} ({start.tzname()})\n"
    )
    greeting = f"Hi {_one_line(user.name)},\n\n"

    match notice:
        case Notice.CONFIRMED:
            subject = f"Booking confirmed: {court}, {when}"
            body = f"Your booking is confirmed.\n\n{details}"
        case Notice.CANCELLED:
            subject = f"Booking cancelled: {court}, {when}"
            body = f"You cancelled this booking.\n\n{details}"
        case Notice.CANCELLED_BY_COURT:
            subject = f"Your booking was cancelled by the court: {court}, {when}"
            body = (
                "The court had to cancel this booking, for example because of maintenance. "
                f"We are sorry for the trouble.\n\n{details}"
            )
        case Notice.REMINDER:
            subject = f"Reminder: {court}, {when}"
            body = f"Your booking is coming up.\n\n{details}"

    message = EmailMessage()
    message["From"] = settings.mail_from
    message["To"] = Address(display_name=_one_line(user.name), addr_spec=user.email)
    message["Subject"] = subject
    message.set_content(greeting + body)
    return message


async def prepare(
    session: AsyncSession, reservation: Reservation, notice: Notice
) -> EmailMessage | None:
    """The email telling the reservation's user about `notice`, or None if it cannot be built.

    Never raises: it runs after the reservation was saved, and an email problem must not turn
    that into an error for the person who booked.
    """
    try:
        resource = await session.get(Resource, reservation.resource_id)
        user = await session.get(User, reservation.user_id)
        return compose(notice, reservation, resource, user)
    except Exception:
        logger.exception("Could not build the %s email for reservation %s", notice, reservation.id)
        return None
