import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import burn_password_check, hash_password, verify_password
from app.db.models import User

UNIQUE_VIOLATION = "23505"


class EmailAlreadyRegistered(Exception):
    pass


class RegistrationClosed(Exception):
    """The account cap (`max_users`) is reached; only the demo's abuse limit uses it."""


class InvalidCredentials(Exception):
    """Wrong password or unknown email; deliberately indistinguishable."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(session: AsyncSession, *, email: str, password: str, name: str) -> User:
    """Create a regular user. Uniqueness is enforced by the database, not by a prior lookup."""
    # A soft cap: two simultaneous sign-ups at the limit may both pass, which is harmless here.
    if settings.max_users > 0 and await session.scalar(select(func.count(User.id))) >= (
        settings.max_users
    ):
        raise RegistrationClosed
    return await _create_user(session, email=email, password=password, name=name, role="user")


async def create_admin(session: AsyncSession, *, email: str, password: str, name: str) -> User:
    """Create an admin. Only the `create-admin` command calls this; no HTTP route may."""
    return await _create_user(session, email=email, password=password, name=name, role="admin")


async def _create_user(
    session: AsyncSession, *, email: str, password: str, name: str, role: str
) -> User:
    user = User(
        email=normalize_email(email),
        password_hash=hash_password(password),
        name=name,
        role=role,
    )
    session.add(user)
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if exc.orig.sqlstate == UNIQUE_VIOLATION:
            raise EmailAlreadyRegistered from exc
        raise
    return user


async def authenticate(session: AsyncSession, *, email: str, password: str) -> User:
    user = await session.scalar(select(User).where(User.email == normalize_email(email)))
    if user is None:
        burn_password_check(password)
        raise InvalidCredentials
    if not verify_password(password, user.password_hash):
        raise InvalidCredentials
    return user


async def get_user(session: AsyncSession, user_id: uuid.UUID) -> User | None:
    return await session.get(User, user_id)
