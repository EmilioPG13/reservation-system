import uuid
from datetime import datetime, time

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    SmallInteger,
    Text,
    Time,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import TSTZRANGE, UUID, ExcludeConstraint, Range
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# Deterministic constraint names keep Alembic migrations (and 23P01 error handling) stable.
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    # Every datetime is timestamptz; naive timestamps are how timezone bugs start.
    type_annotation_map = {datetime: DateTime(timezone=True)}


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )


def _created_at() -> Mapped[datetime]:
    return mapped_column(server_default=func.now())


class User(Base):
    __tablename__ = "users"
    __table_args__ = (CheckConstraint("role IN ('user', 'admin')", name="role_valid"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text, server_default="user")
    created_at: Mapped[datetime] = _created_at()


class Resource(Base):
    """A bookable court. Kept generic: anything reservable by time slots fits."""

    __tablename__ = "resources"
    __table_args__ = (CheckConstraint("slot_minutes > 0", name="slot_minutes_positive"),)

    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, server_default="America/Mexico_City")
    slot_minutes: Mapped[int] = mapped_column(Integer, server_default="60")
    active: Mapped[bool] = mapped_column(Boolean, server_default="true")

    # Replacing the list rewrites the weekly schedule; weekdays left out mean closed.
    opening_hours: Mapped[list["OpeningHours"]] = relationship(
        cascade="all, delete-orphan", lazy="selectin", order_by="OpeningHours.weekday"
    )


class OpeningHours(Base):
    """One opening window per resource and weekday (0 = Monday), in the resource's local time."""

    __tablename__ = "opening_hours"
    __table_args__ = (
        CheckConstraint("weekday BETWEEN 0 AND 6", name="weekday_valid"),
        CheckConstraint("close_time > open_time", name="closes_after_opening"),
    )

    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), primary_key=True
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    open_time: Mapped[time] = mapped_column(Time)
    close_time: Mapped[time] = mapped_column(Time)


class Blackout(Base):
    """A maintenance window during which a resource cannot be booked."""

    __tablename__ = "blackouts"

    id: Mapped[uuid.UUID] = _uuid_pk()
    resource_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("resources.id", ondelete="CASCADE"), index=True
    )
    during: Mapped[Range[datetime]] = mapped_column(TSTZRANGE)
    reason: Mapped[str | None] = mapped_column(Text)


class Reservation(Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint("status IN ('confirmed', 'cancelled')", name="status_valid"),
        # Ranges are stored as [start, end): back-to-back slots must not overlap.
        CheckConstraint(
            "NOT isempty(during) AND lower_inc(during) AND NOT upper_inc(during)"
            " AND NOT lower_inf(during) AND NOT upper_inf(during)",
            name="during_bounded_half_open",
        ),
        # The point of the project: PostgreSQL itself refuses overlapping confirmed bookings.
        ExcludeConstraint(
            ("resource_id", "="),
            ("during", "&&"),
            using="gist",
            where=text("status = 'confirmed'"),
            name="no_overlapping_confirmed",
        ),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    resource_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("resources.id", ondelete="RESTRICT"))
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    during: Mapped[Range[datetime]] = mapped_column(TSTZRANGE)
    status: Mapped[str] = mapped_column(Text, server_default="confirmed")
    created_at: Mapped[datetime] = _created_at()
    cancelled_at: Mapped[datetime | None]
    reminder_sent_at: Mapped[datetime | None]
