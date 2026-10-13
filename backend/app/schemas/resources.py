import uuid
from datetime import date, datetime, time
from typing import Annotated, Self
from zoneinfo import ZoneInfo

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from app.db.models import Blackout
from app.services.availability import CourtDay, SlotStatus


def _check_timezone(value: str) -> str:
    try:
        ZoneInfo(value)
    except (KeyError, ValueError, OSError):
        raise ValueError("must be an IANA time zone name, e.g. America/Mexico_City") from None
    return value


Timezone = Annotated[str, AfterValidator(_check_timezone)]
Name = Annotated[str, Field(min_length=1, max_length=100)]
Description = Annotated[str, Field(max_length=500)]
SlotMinutes = Annotated[int, Field(ge=5, le=480)]


class ResourceCreate(BaseModel):
    name: Name
    description: Description | None = None
    timezone: Timezone = "America/Mexico_City"
    slot_minutes: SlotMinutes = 60


class ResourceUpdate(BaseModel):
    """Only the fields sent are changed; `description` may be set to null to clear it."""

    name: Name | None = None
    description: Description | None = None
    timezone: Timezone | None = None
    slot_minutes: SlotMinutes | None = None
    active: bool | None = None

    @field_validator("name", "timezone", "slot_minutes", "active")
    @classmethod
    def not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("cannot be null")
        return value


class OpeningHoursItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    weekday: int = Field(ge=0, le=6, description="0 = Monday")
    open_time: time = Field(description="Local time of the court")
    close_time: time

    @model_validator(mode="after")
    def check_window(self) -> Self:
        if self.open_time.tzinfo or self.close_time.tzinfo:
            raise ValueError("times are local to the court and must not carry an offset")
        if self.close_time <= self.open_time:
            raise ValueError("close_time must be after open_time")
        return self


class OpeningHoursUpdate(BaseModel):
    hours: list[OpeningHoursItem] = Field(max_length=7)

    @field_validator("hours")
    @classmethod
    def one_window_per_weekday(cls, hours: list[OpeningHoursItem]) -> list[OpeningHoursItem]:
        weekdays = [h.weekday for h in hours]
        if len(set(weekdays)) != len(weekdays):
            raise ValueError("at most one opening window per weekday")
        return hours


class ResourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    timezone: str
    slot_minutes: int
    active: bool
    opening_hours: list[OpeningHoursItem]


class BlackoutCreate(BaseModel):
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: Annotated[str, Field(max_length=200)] | None = None

    @model_validator(mode="after")
    def check_order(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class BlackoutRead(BaseModel):
    id: uuid.UUID
    resource_id: uuid.UUID
    starts_at: datetime
    ends_at: datetime
    reason: str | None

    @classmethod
    def from_blackout(cls, blackout: Blackout) -> Self:
        return cls(
            id=blackout.id,
            resource_id=blackout.resource_id,
            starts_at=blackout.during.lower,
            ends_at=blackout.during.upper,
            reason=blackout.reason,
        )


class SlotRead(BaseModel):
    start: datetime
    end: datetime
    status: SlotStatus
    mine: bool = False  # true on a `booked` slot when the caller holds the reservation


class CourtAvailability(BaseModel):
    id: uuid.UUID
    name: str
    timezone: str
    slot_minutes: int
    slots: list[SlotRead]


class DayAvailability(BaseModel):
    """The whole grid in one response: one entry per active court."""

    date: date
    courts: list[CourtAvailability]

    @classmethod
    def build(cls, day: date, courts: list[CourtDay]) -> Self:
        return cls(
            date=day,
            courts=[
                CourtAvailability(
                    id=c.resource.id,
                    name=c.resource.name,
                    timezone=c.resource.timezone,
                    slot_minutes=c.resource.slot_minutes,
                    slots=[
                        SlotRead(start=s.start, end=s.end, status=s.status, mine=s.mine)
                        for s in c.slots
                    ],
                )
                for c in courts
            ],
        )
