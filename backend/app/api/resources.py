from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Query

from app.api.deps import CurrentUser, SessionDep
from app.schemas.resources import DayAvailability, ResourceRead
from app.services import availability as availability_service
from app.services import resources as resource_service

router = APIRouter(tags=["resources"])


@router.get("/resources")
async def list_resources(_: CurrentUser, session: SessionDep) -> list[ResourceRead]:
    resources = await resource_service.list_resources(session, include_inactive=False)
    return [ResourceRead.model_validate(r) for r in resources]


@router.get("/availability")
async def availability(
    _: CurrentUser,
    session: SessionDep,
    day: Annotated[date, Query(alias="date", description="Local date, read in each court's zone")],
) -> DayAvailability:
    courts = await availability_service.get_day_availability(
        session, day=day, now=datetime.now(UTC)
    )
    return DayAvailability.build(day, courts)
