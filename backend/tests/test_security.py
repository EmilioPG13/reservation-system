"""Password hashing and token handling in isolation: no database, no HTTP."""

from datetime import timedelta

import jwt
import pytest

from app.core.config import settings
from app.core.security import (
    InvalidTokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)

SECRET = settings.jwt_secret_key.get_secret_value()


def test_password_roundtrip_and_wrong_password():
    hashed = hash_password("correct horse")
    assert verify_password("correct horse", hashed)
    assert not verify_password("wrong horse", hashed)


def test_hash_is_argon2_and_salted():
    first, second = hash_password("same"), hash_password("same")
    assert first.startswith("$argon2id$")
    assert first != second


def test_token_roundtrip():
    assert decode_access_token(create_access_token("user-1")) == "user-1"


def test_expired_token_is_rejected():
    token = create_access_token("user-1", expires_delta=timedelta(seconds=-1))
    with pytest.raises(InvalidTokenError):
        decode_access_token(token)


def test_token_signed_with_another_key_is_rejected():
    forged = jwt.encode({"sub": "user-1", "exp": 4102444800}, "not-the-key-" * 4, "HS256")
    with pytest.raises(InvalidTokenError):
        decode_access_token(forged)


def test_unsigned_token_is_rejected():
    unsigned = jwt.encode({"sub": "user-1", "exp": 4102444800}, None, algorithm="none")
    with pytest.raises(InvalidTokenError):
        decode_access_token(unsigned)


@pytest.mark.parametrize(
    "claims", [{"exp": 4102444800}, {"sub": "user-1"}], ids=["no_sub", "no_exp"]
)
def test_token_missing_required_claim_is_rejected(claims: dict):
    with pytest.raises(InvalidTokenError):
        decode_access_token(jwt.encode(claims, SECRET, "HS256"))
