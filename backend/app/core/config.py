from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import make_url

# Query options that Neon, Vercel and libpq put in their URLs. asyncpg cannot take them as is.
_DROPPED_QUERY_OPTIONS = {"channel_binding", "connect_timeout"}


def asyncpg_url(raw: str) -> str:
    """Accept a connection string as a provider hands it out and make it work with asyncpg.

    `postgres://` and `postgresql://` become `postgresql+asyncpg://`, `sslmode=` becomes `ssl=`,
    and options asyncpg does not know are dropped. Anything else is returned unchanged.
    """
    if not raw:
        return raw
    url = make_url(raw)
    if url.drivername not in {"postgres", "postgresql", "postgresql+asyncpg"}:
        return raw
    query = {k: v for k, v in url.query.items() if k not in _DROPPED_QUERY_OPTIONS}
    if "sslmode" in query:
        query.setdefault("ssl", query["sslmode"])
        del query["sslmode"]
    url = url.set(drivername="postgresql+asyncpg", query=query)
    return url.render_as_string(hide_password=False)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "postgresql+asyncpg://booking:booking@localhost:5433/court_booking"
    # Alembic connects here when set. A pooled URL (Neon's -pooler host) is wrong for migrations.
    migration_database_url: str = ""
    # True when `database_url` goes through a transaction-mode pooler such as PgBouncer: asyncpg's
    # prepared-statement cache breaks there.
    database_pooled: bool = False
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
    # A real provider needs both (usually port 587). Mailpit needs neither.
    smtp_username: str = ""
    smtp_password: SecretStr = SecretStr("")
    smtp_start_tls: bool = False
    mail_from: str = "Court Booking <no-reply@courtbooking.local>"

    # Reminder loop (app/workers/reminders.py).
    reminders_enabled: bool = True
    reminder_hours_before: int = 24
    reminder_interval_seconds: float = 60

    # Abuse limits for the public demo. 0 disables a limit.
    max_users: int = 0  # registered accounts, admins included
    auth_attempts_per_minute: int = 10  # per client address, for register and login separately

    # Browser origins allowed to call the API, comma-separated (e.g. the deployed frontend).
    # Empty means no CORS: in development Vite proxies /api, so the browser never crosses origins.
    cors_origins: str = ""

    @field_validator("database_url", "migration_database_url")
    @classmethod
    def _asyncpg(cls, value: str) -> str:
        return asyncpg_url(value)


settings = Settings()
