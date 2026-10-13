import uuid
from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, BaseModel

from app.db.models import Reservation
from app.services.reservations import DayReservation


class ReservationCreate(BaseModel):
    resource_id: uuid.UUID
    starts_at: AwareDatetime  # must be the start of a slot, as `/availability` returns it


class ReservationRead(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    status: str
    created_at: datetime
    cancelled_at: datetime | None

    @classmethod
    def from_reservation(cls, reservation: Reservation) -> Self:
        return cls(
            id=reservation.id,
            resource_id=reservation.resource_id,
            starts_at=reservation.during.lower,
            ends_at=reservation.during.upper,
            status=reservation.status,
            created_at=reservation.created_at,
            cancelled_at=reservation.cancelled_at,
        )


class ReservationPage(BaseModel):
    items: list[ReservationRead]
    total: int
    limit: int
    offset: int


class AdminReservationRead(ReservationRead):
    """A reservation with who made it; only admins ever receive this."""

    resource_name: str
    user_id: uuid.UUID
    user_name: str
    user_email: str

    @classmethod
    def from_day_reservation(cls, row: DayReservation) -> Self:
        base = ReservationRead.from_reservation(row.reservation)
        return cls(
            **base.model_dump(),
            resource_name=row.resource.name,
            user_id=row.user.id,
            user_name=row.user.name,
            user_email=row.user.email,
        )
