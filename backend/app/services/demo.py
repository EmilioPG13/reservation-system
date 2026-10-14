"""Demo data for the public deployment: courts, sample players and a few reservations.

Everything goes through the same services the API uses, so the sample reservations obey the real
rules (opening hours, the per-user limit, the exclusion constraint). Running it again only tops
up what is missing.
"""

import random
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, time, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.db.models import Reservation, Resource, User
from app.services import availability, reservations, resources

COURTS = 10
OPENS, CLOSES = time(8), time(22)
PLAYERS = 12
DAYS_AHEAD = 3
PLAYER_EMAIL = "player{number:02d}@demo.example"


@dataclass
class SeedResult:
    courts_created: int
    players_created: int
    reservations_created: int


async def _ensure_courts(session: AsyncSession) -> int:
    if await session.scalar(select(func.count(Resource.id))):
        return 0  # an admin already manages the courts; do not add to them
    for number in range(1, COURTS + 1):
        court = await resources.create_resource(
            session,
            name=f"Cancha {number}",
            description=None,
            timezone="America/Mexico_City",
            slot_minutes=60,
        )
        await resources.set_opening_hours(
            session, court.id, [(weekday, OPENS, CLOSES) for weekday in range(7)]
        )
    return COURTS


async def _ensure_players(session: AsyncSession) -> tuple[list[User], int]:
    emails = [PLAYER_EMAIL.format(number=n) for n in range(1, PLAYERS + 1)]
    existing = {
        u.email: u for u in await session.scalars(select(User).where(User.email.in_(emails)))
    }
    created = 0
    for number, email in enumerate(emails, start=1):
        if email not in existing:
            # Nobody logs in as a sample player, so the password is random and thrown away.
            existing[email] = User(
                email=email,
                name=f"Jugador {number}",
                password_hash=hash_password(secrets.token_urlsafe(24)),
            )
            session.add(existing[email])
            created += 1
    await session.commit()
    return [existing[e] for e in emails], created


async def seed(session: AsyncSession, *, now: datetime) -> SeedResult:
    courts_created = await _ensure_courts(session)
    players, players_created = await _ensure_players(session)

    made = 0
    for offset in range(DAYS_AHEAD):
        day = (now + timedelta(days=offset)).date()
        free = [
            (court.resource.id, slot.start)
            for court in await availability.get_day_availability(session, day=day, now=now)
            for slot in court.slots
            if slot.status is availability.SlotStatus.AVAILABLE
        ]
        random.Random(day.toordinal()).shuffle(free)  # same day, same picture
        # One booking per player and day, so the per-user limit spreads them over the days.
        for player, (court_id, starts_at) in zip(players, free, strict=False):
            try:
                await reservations.book(
                    session,
                    user_id=player.id,
                    resource_id=court_id,
                    starts_at=starts_at,
                    now=now,
                )
            except reservations.TooManyActiveReservations:
                continue
            made += 1
    return SeedResult(courts_created, players_created, made)


async def prune(session: AsyncSession, *, older_than_days: int, now: datetime | None = None) -> int:
    """Delete reservations of non-admin users that ended more than `older_than_days` ago.

    Keeps the free database small. Cancelled ones go too: nobody reads that history in a demo.
    """
    cutoff = (now or datetime.now(UTC)) - timedelta(days=older_than_days)
    admins = select(User.id).where(User.role == "admin")
    result = await session.execute(
        delete(Reservation).where(
            func.upper(Reservation.during) < cutoff, Reservation.user_id.not_in(admins)
        )
    )
    await session.commit()
    return result.rowcount
