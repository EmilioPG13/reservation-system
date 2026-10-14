"""Connection strings are accepted the way the database providers hand them out."""

import pytest

from app.core.config import asyncpg_url

NEON = "postgresql://neondb_owner:pw@ep-x-pooler.c-14.us-east-1.aws.neon.tech/neondb"
EXPECTED = "postgresql+asyncpg://neondb_owner:pw@ep-x-pooler.c-14.us-east-1.aws.neon.tech/neondb"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (f"{NEON}?channel_binding=require&sslmode=require", f"{EXPECTED}?ssl=require"),
        (f"{NEON}?sslmode=require", f"{EXPECTED}?ssl=require"),
        (NEON.replace("postgresql", "postgres"), EXPECTED),
        (
            f"{NEON}?channel_binding=require&connect_timeout=15&sslmode=require",
            f"{EXPECTED}?ssl=require",
        ),
        (f"{EXPECTED}?ssl=require", f"{EXPECTED}?ssl=require"),  # already right
        (
            "postgresql+asyncpg://booking:booking@localhost:5433/court_booking",
            "postgresql+asyncpg://booking:booking@localhost:5433/court_booking",
        ),
        ("", ""),
        ("sqlite:///x.db", "sqlite:///x.db"),
    ],
)
def test_provider_urls_are_made_asyncpg_ready(raw: str, expected: str):
    assert asyncpg_url(raw) == expected


def test_a_password_with_special_characters_survives():
    raw = "postgresql://u:p%40ss%2Fw@host/db?sslmode=require"

    assert asyncpg_url(raw) == "postgresql+asyncpg://u:p%40ss%2Fw@host/db?ssl=require"
