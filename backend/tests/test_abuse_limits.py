"""The public demo's guards: attempts per minute and the cap on accounts."""

import pytest
from httpx import AsyncClient

from app.core.config import settings

PASSWORD = "correct horse battery"


async def test_login_is_refused_after_too_many_attempts(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "auth_attempts_per_minute", 3)
    form = {"username": "nobody@example.com", "password": PASSWORD}

    codes = [(await api_client.post("/auth/login", data=form)).status_code for _ in range(4)]

    assert codes == [401, 401, 401, 429]
    blocked = await api_client.post("/auth/login", data=form)
    assert int(blocked.headers["Retry-After"]) >= 1


async def test_register_and_login_count_separately(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "auth_attempts_per_minute", 1)
    form = {"username": "nobody@example.com", "password": PASSWORD}
    await api_client.post("/auth/login", data=form)

    response = await api_client.post(
        "/auth/register", json={"email": "ana@example.com", "password": PASSWORD, "name": "Ana"}
    )

    assert response.status_code == 201


async def test_a_zero_limit_means_unlimited(
    api_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "auth_attempts_per_minute", 0)
    form = {"username": "nobody@example.com", "password": PASSWORD}

    codes = {(await api_client.post("/auth/login", data=form)).status_code for _ in range(15)}

    assert codes == {401}


async def test_registration_closes_at_the_account_cap(
    api_client: AsyncClient, user, monkeypatch: pytest.MonkeyPatch
):
    monkeypatch.setattr(settings, "max_users", 1)  # the `user` fixture already fills it

    response = await api_client.post(
        "/auth/register", json={"email": "ana@example.com", "password": PASSWORD, "name": "Ana"}
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Registration is closed"
