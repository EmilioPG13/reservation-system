# Court Booking

FastAPI + PostgreSQL + React court reservation app. Portfolio project; the point is no double bookings via a PostgreSQL exclusion constraint.

Project notes: `C:\Users\Emili\Documents\Obsidian Vault\Work\Coding\Reservation System\Reservation System.md`
Plan and handoff (Spanish): `C:\Users\Emili\Documents\Obsidian Vault\Work\Coding\Reservation System\docs\`. The plan is the source for phases and scope; there is no `docs/` in this repo.

## Conventions and gotchas
- Backend commands run from `backend/` with `uv run ...`. Windows: `npm.cmd`, no `&&` in PowerShell.
- Dev Postgres is on host port **5433** (5432 is taken by another Postgres on this machine). Tests use the separate `court_booking_test` database.
- Routers hold no business rules; services know nothing about HTTP (see plan, section 5).
- Dates are UTC in the database, ranges `[)`.
- The whole frontend is designed and built with the `impeccable` skill, not freehand. The court grid's accessibility rules (plan, section 6) are inputs to it, not up for redesign.
- Frontend: `frontend/`, run with `npm.cmd`. TypeScript stays on 5.x because `openapi-typescript` declares it as a peer. After an API change run `uv run python -m app.export_openapi ../frontend/openapi.json` in `backend/`, then `npm.cmd run api:types`. In development the SPA calls the API under `/api` (Vite proxy); a deployed build uses `VITE_API_URL` and the API needs that origin in `CORS_ORIGINS`.
- `npm.cmd run test:e2e` needs the whole stack up (Docker Desktop, API on :8000, `npm.cmd run dev`). Test emails need a real-looking domain: `EmailStr` rejects `.test`.
