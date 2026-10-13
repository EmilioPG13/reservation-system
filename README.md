# Court Booking

Padel court reservations where double bookings are impossible by construction: PostgreSQL itself rejects overlapping reservations (exclusion constraint on a time range), instead of the application checking first and hoping.

Work in progress. Phase 0 (skeleton) only.

## Run locally

```powershell
docker compose up -d --wait        # PostgreSQL 17 on :5433, Mailpit UI on :8025
cd backend
uv sync
uv run uvicorn app.main:app --reload   # http://localhost:8000/health, /docs
uv run pytest                          # needs the compose Postgres running
uv run ruff check . ; uv run ruff format --check .
```
