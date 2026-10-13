import uuid

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import burn_password_check, hash_password, verify_password
from app.db.models import User

UNIQUE_VIOLATION = "23505"


class EmailAlreadyRegistered(Exception):
    pass


class InvalidCredentials(Exception):
    """Wrong password or unknown email; deliberately indistinguishable."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(session: AsyncSession, *, email: str, password: str, name: str) -> User:
    """Create a regular user. Uniqueness is enforced by the database, not by a prior lookup."""
    user = User(email=normalize_email(email), password_hash=hash_password(password), name=name)
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
