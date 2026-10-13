import uuid
from collections.abc import Sequence
from datetime import datetime, time
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import Range
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import Blackout, OpeningHours, Resource

UPDATABLE_FIELDS = {"name", "description", "timezone", "slot_minutes", "active"}


class ResourceNotFound(Exception):
    pass


class BlackoutNotFound(Exception):
    pass


async def list_resources(session: AsyncSession, *, include_inactive: bool) -> list[Resource]:
    query = select(Resource).order_by(Resource.name)
    if not include_inactive:
        query = query.where(Resource.active)
    return list(await session.scalars(query))


async def get_resource(session: AsyncSession, resource_id: uuid.UUID) -> Resource:
    # populate_existing: a court already in this session may not have its schedule loaded, and
    # a lazy load inside an async request would fail.
    resource = await session.get(Resource, resource_id, populate_existing=True)
    if resource is None:
        raise ResourceNotFound
    return resource


async def create_resource(
    session: AsyncSession,
    *,
    name: str,
    description: str | None,
    timezone: str,
    slot_minutes: int,
) -> Resource:
    resource = Resource(
        name=name,
        description=description,
        timezone=timezone,
        slot_minutes=slot_minutes,
        opening_hours=[],  # a new court is closed until the admin sets a schedule
    )
    session.add(resource)
    await session.commit()
    return resource


async def update_resource(
    session: AsyncSession, resource_id: uuid.UUID, changes: dict[str, Any]
) -> Resource:
    """Apply a partial update. Courts are deactivated (`active=False`), never deleted."""
    resource = await get_resource(session, resource_id)
    for field, value in changes.items():
        if field in UPDATABLE_FIELDS:
            setattr(resource, field, value)
    await session.commit()
    return resource


async def set_opening_hours(
    session: AsyncSession, resource_id: uuid.UUID, hours: Sequence[tuple[int, time, time]]
) -> Resource:
    """Replace the weekly schedule. `hours` holds (weekday, open, close), weekday 0 = Monday."""
    resource = await get_resource(session, resource_id)
    resource.opening_hours = [
        OpeningHours(weekday=weekday, open_time=opens, close_time=closes)
        for weekday, opens, closes in hours
    ]
    await session.commit()
    return resource


async def list_blackouts(session: AsyncSession, resource_id: uuid.UUID) -> list[Blackout]:
    await get_resource(session, resource_id)
    return list(
        await session.scalars(
            select(Blackout).where(Blackout.resource_id == resource_id).order_by(Blackout.during)
        )
    )


async def create_blackout(
    session: AsyncSession,
    resource_id: uuid.UUID,
    *,
    starts_at: datetime,
    ends_at: datetime,
    reason: str | None,
) -> Blackout:
    """Block [starts_at, ends_at). Existing reservations in the window are left untouched."""
    await get_resource(session, resource_id)
    blackout = Blackout(
        resource_id=resource_id, during=Range(starts_at, ends_at, bounds="[)"), reason=reason
    )
    session.add(blackout)
    await session.commit()
    return blackout


async def delete_blackout(
    session: AsyncSession, resource_id: uuid.UUID, blackout_id: uuid.UUID
) -> None:
    blackout = await session.get(Blackout, blackout_id)
    # A blackout of another court is reported as missing, not as forbidden.
    if blackout is None or blackout.resource_id != resource_id:
        raise BlackoutNotFound
    await session.delete(blackout)
    await session.commit()
