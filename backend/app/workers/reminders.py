"""The reminder loop: an email `reminder_hours_before` hours ahead of each confirmed reservation.

It lives inside the API process, with no queue. That is why the hosting must keep the process
awake (plan, section 8).

A reminder is marked as sent *before* it is sent. If the process dies or the mail server is down
in between, that reminder is lost; the alternative, marking after, would send it twice instead.
Missing one email is better than repeating it.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models import Reservation
from app.db.session import SessionFactory
from app.services import mailer, notifications
from app.services.availability import CONFIRMED
from app.services.notifications import Notice

logger = logging.getLogger(__name__)


async def claim_due(session: AsyncSession, now: datetime) -> list[Reservation]:
    """Mark the reservations that need a reminder now as reminded, and return them.

    One statement both finds and marks them, so two copies of the app running at once (or two
    overlapping passes) never claim the same reservation: `skip locked` leaves a row another pass
    is already holding.

    A reservation made inside the window (booked tomorrow morning for tomorrow evening) is not
    reminded: its confirmation, sent minutes ago, already says everything the reminder would.
    """
    ahead = timedelta(hours=settings.reminder_hours_before)
    starts_at = func.lower(Reservation.during)
    due = (
        select(Reservation.id)
        .where(
            Reservation.status == CONFIRMED,
            Reservation.reminder_sent_at.is_(None),
            starts_at > now,
            starts_at <= now + ahead,
            Reservation.created_at <= starts_at - ahead,
        )
        .with_for_update(skip_locked=True)
    )
    claimed = await session.scalars(
        update(Reservation)
        .where(Reservation.id.in_(due))
        .values(reminder_sent_at=now)
        .returning(Reservation)
    )
    reservations = list(claimed)
    await session.commit()
    return reservations


async def send_due_reminders(session: AsyncSession, now: datetime) -> int:
    """One pass of the loop. Returns how many reminders the mail server accepted."""
    sent = 0
    for reservation in await claim_due(session, now):
        message = await notifications.prepare(session, reservation, Notice.REMINDER)
        if message is not None and await mailer.send_safely(message):
            sent += 1
    return sent


async def run_forever() -> None:
    """Run a pass every `reminder_interval_seconds` until cancelled. A failed pass is logged."""
    while True:
        try:
            async with SessionFactory() as session:
                await send_due_reminders(session, datetime.now(UTC))
        except Exception:
            logger.exception("Reminder pass failed")
        await asyncio.sleep(settings.reminder_interval_seconds)
