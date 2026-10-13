# Court Booking

FastAPI + PostgreSQL + React court reservation app. Portfolio project; the point is no double bookings via a PostgreSQL exclusion constraint.

Project notes: `C:\Users\Emili\Documents\Obsidian Vault\Work\Coding\Reservation System\Reservation System.md`
Plan and handoff (Spanish): `C:\Users\Emili\Documents\Obsidian Vault\Work\Coding\Reservation System\docs\`. The plan is the source for phases and scope; there is no `docs/` in this repo.

## Conventions and gotchas
- Backend commands run from `backend/` with `uv run ...`. Windows: `npm.cmd`, no `&&` in PowerShell.
- Dev Postgres is on host port **5433** (5432 is taken by another Postgres on this machine). Tests use the separate `court_booking_test` database.
- Routers hold no business rules; services know nothing about HTTP (see plan, section 5).
- Dates are UTC in the database, ranges `[)`.
