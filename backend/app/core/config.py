from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5433/court_booking"
    test_database_url: str = (
        "postgresql+asyncpg://booking:booking@localhost:5433/court_booking_test"
    )


settings = Settings()
