import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, SessionDep
from app.db.models import Reservation
from app.schemas.reservations import ReservationCreate, ReservationPage, ReservationRead
from app.services import mailer, notifications
from app.services import reservations as reservation_service
from app.services.notifications import Notice
from app.services.resources import ResourceNotFound

router = APIRouter(prefix="/reservations", tags=["reservations"])

# 409 is reserved for "someone else holds that slot", so the client can tell it apart from every
# other refusal (limit reached, slot in the past...), which are all 422.
UNPROCESSABLE = status.HTTP_422_UNPROCESSABLE_CONTENT


def reservation_http_error(exc: Exception) -> HTTPException:
    """Translate a service exception into the HTTP answer for it."""
    match exc:
        case ResourceNotFound():
            return HTTPException(status.HTTP_404_NOT_FOUND, "Court not found")
        case reservation_service.ReservationNotFound():
            return HTTPException(status.HTTP_404_NOT_FOUND, "Reservation not found")
        case reservation_service.SlotTaken():
            return HTTPException(status.HTTP_409_CONFLICT, "That slot was just taken")
        case reservation_service.AlreadyCancelled():
            return HTTPException(status.HTTP_409_CONFLICT, "Reservation is already cancelled")
        case reservation_service.NotASlot():
            return HTTPException(
                UNPROCESSABLE, "That time is not the start of a slot of this court"
            )
        case reservation_service.SlotInPast():
            return HTTPException(UNPROCESSABLE, "That slot has already started")
        case reservation_service.SlotBlocked():
            return HTTPException(UNPROCESSABLE, "That slot is blocked for maintenance")
        case reservation_service.TooManyActiveReservations(limit=limit):
            return HTTPException(
                UNPROCESSABLE, f"You already have the maximum of {limit} active reservations"
            )
        case reservation_service.CancellationTooLate(hours=hours):
            return HTTPException(
                UNPROCESSABLE, f"Reservations cannot be cancelled less than {hours} hours ahead"
            )
    raise exc


HANDLED = (ResourceNotFound, reservation_service.ReservationError)


async def queue_email(
    background: BackgroundTasks, session: AsyncSession, reservation: Reservation, notice: Notice
) -> None:
    """Send the email after the response, so a slow or failing mail server never shows."""
    message = await notifications.prepare(session, reservation, notice)
    if message is not None:
        background.add_task(mailer.send_safely, message)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_reservation(
    body: ReservationCreate, user: CurrentUser, session: SessionDep, background: BackgroundTasks
) -> ReservationRead:
    try:
        reservation = await reservation_service.book(
            session,
            user_id=user.id,
            resource_id=body.resource_id,
            starts_at=body.starts_at,
            now=datetime.now(UTC),
        )
    except HANDLED as exc:
        raise reservation_http_error(exc) from None
    await queue_email(background, session, reservation, Notice.CONFIRMED)
    return ReservationRead.from_reservation(reservation)


@router.get("")
async def my_reservations(
    user: CurrentUser,
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ReservationPage:
    reservations, total = await reservation_service.list_for_user(
        session, user.id, limit=limit, offset=offset
    )
    return ReservationPage(
        items=[ReservationRead.from_reservation(r) for r in reservations],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.post("/{reservation_id}/cancel")
async def cancel_reservation(
    reservation_id: uuid.UUID, user: CurrentUser, session: SessionDep, background: BackgroundTasks
) -> ReservationRead:
    try:
        reservation = await reservation_service.cancel_own(
            session, reservation_id, user_id=user.id, now=datetime.now(UTC)
        )
    except HANDLED as exc:
        raise reservation_http_error(exc) from None
    await queue_email(background, session, reservation, Notice.CANCELLED)
    return ReservationRead.from_reservation(reservation)
