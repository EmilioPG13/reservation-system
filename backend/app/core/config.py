from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5433/court_booking"
    test_database_url: str = (
        "postgresql+asyncpg://booking:booking@localhost:5433/court_booking_test"
    )

    # No default on purpose: a hardcoded key that reaches production lets anyone forge tokens.
    jwt_secret_key: SecretStr
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 30


settings = Settings()
