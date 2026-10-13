"""Register, login and the `current user` / `admin only` dependencies, end to end over HTTP."""

import uuid
from collections.abc import AsyncIterator
from datetime import timedelta

import jwt
import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, CurrentUser
from app.core.security import create_access_token, hash_password
from app.db.models import User
from app.db.session import get_session

PASSWORD = "correct horse battery"


def register_body(email: str = "ana@example.com", **overrides: str) -> dict[str, str]:
    return {"email": email, "password": PASSWORD, "name": "Ana", **overrides}


async def login(client: AsyncClient, email: str = "ana@example.com", password: str = PASSWORD):
    return await client.post("/auth/login", data={"username": email, "password": password})


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def register_and_login(client: AsyncClient) -> str:
    assert (await client.post("/auth/register", json=register_body())).status_code == 201
    return (await login(client)).json()["access_token"]


# --- registration ---------------------------------------------------------------------------


async def test_register_creates_a_regular_user_without_leaking_the_hash(
    api_client: AsyncClient, session: AsyncSession
):
    response = await api_client.post("/auth/register", json=register_body())

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "ana@example.com"
    assert body["role"] == "user"
    assert "password" not in body and "password_hash" not in body
    stored = await session.scalar(select(User).where(User.email == "ana@example.com"))
    assert stored.password_hash.startswith("$argon2id$")
    assert PASSWORD not in stored.password_hash


async def test_register_cannot_choose_a_role(api_client: AsyncClient):
    response = await api_client.post("/auth/register", json=register_body(role="admin"))

    assert response.status_code == 201
    assert response.json()["role"] == "user"


@pytest.mark.parametrize("second_email", ["ana@example.com", "  ANA@Example.com "])
async def test_register_duplicate_email_is_a_conflict(api_client: AsyncClient, second_email: str):
    assert (await api_client.post("/auth/register", json=register_body())).status_code == 201

    response = await api_client.post("/auth/register", json=register_body(second_email))

    assert response.status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [{"email": "not-an-email"}, {"password": "short"}, {"password": "x" * 129}, {"name": ""}],
    ids=["bad_email", "short_password", "huge_password", "empty_name"],
)
async def test_register_rejects_invalid_input(api_client: AsyncClient, overrides: dict[str, str]):
    response = await api_client.post("/auth/register", json=register_body(**overrides))

    assert response.status_code == 422


# --- login ----------------------------------------------------------------------------------


async def test_login_returns_a_token_that_identifies_the_user(api_client: AsyncClient):
    token = await register_and_login(api_client)

    me = await api_client.get("/auth/me", headers=bearer(token))

    assert me.status_code == 200
    assert me.json()["email"] == "ana@example.com"


async def test_login_is_case_insensitive_on_email(api_client: AsyncClient):
    await api_client.post("/auth/register", json=register_body())

    assert (await login(api_client, "ANA@example.com")).status_code == 200


async def test_wrong_password_and_unknown_email_look_identical(api_client: AsyncClient):
    await api_client.post("/auth/register", json=register_body())

    wrong_password = await login(api_client, password="not the password")
    unknown_email = await login(api_client, email="nobody@example.com")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.headers["www-authenticate"] == "Bearer"


# --- current user ---------------------------------------------------------------------------


async def test_me_without_a_token_is_unauthorized(api_client: AsyncClient):
    response = await api_client.get("/auth/me")

    assert response.status_code == 401


async def test_me_with_a_garbage_token_is_unauthorized(api_client: AsyncClient):
    response = await api_client.get("/auth/me", headers=bearer("not.a.jwt"))

    assert response.status_code == 401


async def test_me_with_an_expired_token_is_unauthorized(api_client: AsyncClient, user: User):
    token = create_access_token(str(user.id), expires_delta=timedelta(seconds=-1))

    response = await api_client.get("/auth/me", headers=bearer(token))

    assert response.status_code == 401


async def test_me_with_a_token_signed_by_someone_else_is_unauthorized(
    api_client: AsyncClient, user: User
):
    forged = jwt.encode({"sub": str(user.id), "exp": 4102444800}, "attacker-key" * 4, "HS256")

    response = await api_client.get("/auth/me", headers=bearer(forged))

    assert response.status_code == 401


@pytest.mark.parametrize("sub", ["not-a-uuid", str(uuid.uuid4())], ids=["malformed", "deleted"])
async def test_me_with_a_token_for_a_nonexistent_user_is_unauthorized(
    api_client: AsyncClient, sub: str
):
    response = await api_client.get("/auth/me", headers=bearer(create_access_token(sub)))

    assert response.status_code == 401


# --- admin only -----------------------------------------------------------------------------


@pytest.fixture
async def guarded_client(session: AsyncSession) -> AsyncIterator[AsyncClient]:
    """A throwaway app with an admin-only route: the real ones arrive in Phase 3."""
    guarded = FastAPI()

    @guarded.get("/admin-only")
    async def admin_only(admin: AdminUser) -> dict[str, str]:
        return {"admin": admin.email}

    @guarded.get("/any-user")
    async def any_user(user: CurrentUser) -> dict[str, str]:
        return {"user": user.email}

    async def _session() -> AsyncIterator[AsyncSession]:
        yield session

    guarded.dependency_overrides[get_session] = _session
    async with AsyncClient(transport=ASGITransport(app=guarded), base_url="http://test") as c:
        yield c


async def make_user(session: AsyncSession, email: str, role: str) -> User:
    account = User(email=email, password_hash=hash_password(PASSWORD), name=role, role=role)
    session.add(account)
    await session.flush()
    return account


async def test_admin_route_rejects_anonymous_with_401(guarded_client: AsyncClient):
    assert (await guarded_client.get("/admin-only")).status_code == 401


async def test_admin_route_rejects_a_regular_user_with_403(
    guarded_client: AsyncClient, session: AsyncSession
):
    member = await make_user(session, "member@example.com", "user")

    response = await guarded_client.get(
        "/admin-only", headers=bearer(create_access_token(str(member.id)))
    )

    assert response.status_code == 403


async def test_admin_route_admits_an_admin(guarded_client: AsyncClient, session: AsyncSession):
    boss = await make_user(session, "boss@example.com", "admin")

    response = await guarded_client.get(
        "/admin-only", headers=bearer(create_access_token(str(boss.id)))
    )

    assert response.status_code == 200
    assert response.json() == {"admin": "boss@example.com"}


async def test_regular_user_can_use_a_non_admin_route(
    guarded_client: AsyncClient, session: AsyncSession
):
    member = await make_user(session, "member@example.com", "user")

    response = await guarded_client.get(
        "/any-user", headers=bearer(create_access_token(str(member.id)))
    )

    assert response.status_code == 200
