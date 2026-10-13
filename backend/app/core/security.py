from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

from app.core.config import settings

# Re-exported so callers can catch it without importing PyJWT.
InvalidTokenError = jwt.InvalidTokenError

_password_hash = PasswordHash.recommended()  # argon2id
# Verified against when an email is unknown, so a login costs the same either way and
# response time does not reveal which emails are registered.
_DUMMY_HASH = _password_hash.hash("not-a-real-password")


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    return _password_hash.verify(password, password_hash)


def burn_password_check(password: str) -> None:
    _password_hash.verify(password, _DUMMY_HASH)


def create_access_token(subject: str, expires_delta: timedelta | None = None) -> str:
    expires_delta = expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": subject, "exp": datetime.now(UTC) + expires_delta}
    return jwt.encode(
        payload, settings.jwt_secret_key.get_secret_value(), algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> str:
    """Return the token's subject, or raise InvalidTokenError (forged, expired or malformed)."""
    payload = jwt.decode(
        token,
        settings.jwt_secret_key.get_secret_value(),
        # A fixed allow-list: never let the token header pick the algorithm ("none" attack).
        algorithms=[settings.jwt_algorithm],
        options={"require": ["exp", "sub"]},
    )
    return payload["sub"]
