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

    # Business rules for reservations.
    max_active_reservations: int = 3  # per user, counting those that have not ended yet
    cancellation_window_hours: int = 12  # users cannot cancel closer to the start than this

    # Outgoing mail. The defaults point at Mailpit from docker-compose.
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_timeout_seconds: float = 10
    mail_from: str = "Court Booking <no-reply@courtbooking.local>"

    # Reminder loop (app/workers/reminders.py).
    reminders_enabled: bool = True
    reminder_hours_before: int = 24
    reminder_interval_seconds: float = 60


settings = Settings()
