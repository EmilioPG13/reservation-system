from fastapi import FastAPI

from app.api import admin, auth, health, resources


def create_app() -> FastAPI:
    app = FastAPI(title="Court Booking")
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(resources.router)
    app.include_router(admin.router)
    return app


app = create_app()
