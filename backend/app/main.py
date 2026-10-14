import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, auth, health, reservations, resources
from app.core.config import settings
from app.workers import reminders


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    loop = asyncio.create_task(reminders.run_forever()) if settings.reminders_enabled else None
    try:
        yield
    finally:
        if loop is not None:
            loop.cancel()
            with suppress(asyncio.CancelledError):
                await loop


def create_app() -> FastAPI:
    app = FastAPI(title="Court Booking", lifespan=lifespan)
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if origins:
        # Tokens travel in the Authorization header, never in cookies, so credentials stay off.
        app.add_middleware(
            CORSMiddleware,
            allow_origins=origins,
            allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
            allow_headers=["Authorization", "Content-Type"],
        )
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(resources.router)
    app.include_router(reservations.router)
    app.include_router(admin.router)
    return app


app = create_app()
