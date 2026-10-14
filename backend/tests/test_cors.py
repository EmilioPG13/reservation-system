from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import create_app

ORIGIN = "https://court-booking.example.com"


def preflight(origin: str) -> dict[str, str]:
    return {
        "Origin": origin,
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    }


async def options(origin: str):
    async with AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    ) as client:
        return await client.options("/reservations", headers=preflight(origin))


async def test_no_origin_is_allowed_by_default() -> None:
    response = await options(ORIGIN)
    assert "access-control-allow-origin" not in response.headers


async def test_a_configured_origin_may_call_with_a_bearer_token(monkeypatch) -> None:
    monkeypatch.setattr(settings, "cors_origins", f" {ORIGIN} , https://other.example.com")
    response = await options(ORIGIN)
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "authorization" in response.headers["access-control-allow-headers"].lower()
    # Tokens are not cookies, so the browser is never told to send credentials.
    assert "access-control-allow-credentials" not in response.headers


async def test_an_unlisted_origin_is_refused(monkeypatch) -> None:
    monkeypatch.setattr(settings, "cors_origins", ORIGIN)
    response = await options("https://evil.example.com")
    assert "access-control-allow-origin" not in response.headers
