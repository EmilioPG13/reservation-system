import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status

from app.api.deps import SessionDep, require_admin
from app.schemas.resources import (
    BlackoutCreate,
    BlackoutRead,
    OpeningHoursUpdate,
    ResourceCreate,
    ResourceRead,
    ResourceUpdate,
)
from app.services import resources as resource_service

# Every route here needs an admin: 401 without a token, 403 for a regular user.
router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

COURT_NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Court not found")


@router.get("/resources")
async def list_resources(session: SessionDep) -> list[ResourceRead]:
    resources = await resource_service.list_resources(session, include_inactive=True)
    return [ResourceRead.model_validate(r) for r in resources]


@router.post("/resources", status_code=status.HTTP_201_CREATED)
async def create_resource(body: ResourceCreate, session: SessionDep) -> ResourceRead:
    resource = await resource_service.create_resource(session, **body.model_dump())
    return ResourceRead.model_validate(resource)


@router.get("/resources/{resource_id}")
async def get_resource(resource_id: uuid.UUID, session: SessionDep) -> ResourceRead:
    try:
        resource = await resource_service.get_resource(session, resource_id)
    except resource_service.ResourceNotFound:
        raise COURT_NOT_FOUND from None
    return ResourceRead.model_validate(resource)


@router.patch("/resources/{resource_id}")
async def update_resource(
    resource_id: uuid.UUID, body: ResourceUpdate, session: SessionDep
) -> ResourceRead:
    try:
        resource = await resource_service.update_resource(
            session, resource_id, body.model_dump(exclude_unset=True)
        )
    except resource_service.ResourceNotFound:
        raise COURT_NOT_FOUND from None
    return ResourceRead.model_validate(resource)


@router.put("/resources/{resource_id}/opening-hours")
async def set_opening_hours(
    resource_id: uuid.UUID, body: OpeningHoursUpdate, session: SessionDep
) -> ResourceRead:
    try:
        resource = await resource_service.set_opening_hours(
            session, resource_id, [(h.weekday, h.open_time, h.close_time) for h in body.hours]
        )
    except resource_service.ResourceNotFound:
        raise COURT_NOT_FOUND from None
    return ResourceRead.model_validate(resource)


@router.get("/resources/{resource_id}/blackouts")
async def list_blackouts(resource_id: uuid.UUID, session: SessionDep) -> list[BlackoutRead]:
    try:
        blackouts = await resource_service.list_blackouts(session, resource_id)
    except resource_service.ResourceNotFound:
        raise COURT_NOT_FOUND from None
    return [BlackoutRead.from_blackout(b) for b in blackouts]


@router.post("/resources/{resource_id}/blackouts", status_code=status.HTTP_201_CREATED)
async def create_blackout(
    resource_id: uuid.UUID, body: BlackoutCreate, session: SessionDep
) -> BlackoutRead:
    try:
        blackout = await resource_service.create_blackout(
            session,
            resource_id,
            starts_at=body.starts_at,
            ends_at=body.ends_at,
            reason=body.reason,
        )
    except resource_service.ResourceNotFound:
        raise COURT_NOT_FOUND from None
    return BlackoutRead.from_blackout(blackout)


@router.delete(
    "/resources/{resource_id}/blackouts/{blackout_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_blackout(
    resource_id: uuid.UUID, blackout_id: uuid.UUID, session: SessionDep
) -> Response:
    try:
        await resource_service.delete_blackout(session, resource_id, blackout_id)
    except resource_service.BlackoutNotFound:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Blackout not found"
        ) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)
