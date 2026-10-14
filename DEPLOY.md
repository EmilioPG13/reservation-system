# Deploying

Neon (PostgreSQL) + Northflank (API, always on, because the reminder loop lives in the process) + Vercel (static frontend). Render's free plan is the fallback for the API but it sleeps, which stops reminders.

Free-tier limits change without notice; recheck them before relying on this.

## 1. Database (Neon)

1. Create a project on PostgreSQL 17. `btree_gist` is supported; the first migration creates the extension.
2. Copy two connection strings exactly as the provider shows them (no editing; the app turns `postgresql://` into `postgresql+asyncpg://`, `sslmode` into `ssl`, and drops `channel_binding`):
   - **Direct** host (no `-pooler`, `DATABASE_URL_UNPOOLED` on Vercel) goes in `MIGRATION_DATABASE_URL`.
   - **Pooled** host (`-pooler`, `DATABASE_URL` on Vercel) goes in `DATABASE_URL`, together with `DATABASE_POOLED=true`. Neon's pooler is PgBouncer in transaction mode, which breaks asyncpg's prepared-statement cache; that flag turns the cache off.
3. Neon suspends idle compute after 5 minutes. The first request afterwards is slower; the interface shows a loading state.

## 2. API (Northflank)

Northflank needs a payment method on file to create resources, even on the free Sandbox plan. Check the plan's CPU and RAM on its pricing page; the API is one small process.

1. New combined service from this GitHub repo: build context `/backend`, Dockerfile `/backend/Dockerfile`, port 8000 (HTTP, public), health check `GET /health`.
2. Runtime variables:

   | Variable | Value |
   |---|---|
   | `JWT_SECRET_KEY` | a fresh random string |
   | `DATABASE_URL` / `DATABASE_POOLED` / `MIGRATION_DATABASE_URL` | from step 1 |
   | `CORS_ORIGINS` | the Vercel URL, e.g. `https://court-booking.vercel.app` |
   | `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USERNAME`, `SMTP_PASSWORD`, `SMTP_START_TLS=true`, `MAIL_FROM` | an SMTP provider; without one emails fail and are only logged |
   | `MAX_USERS`, `AUTH_ATTEMPTS_PER_MINUTE` | abuse limits, e.g. 300 and 10 |

   The container applies migrations on every start.
3. Keep it at one instance. The rate limiter counts in memory.

## 3. Frontend (Vercel)

Import the repo with root directory `frontend`. Set `VITE_API_URL` to the Northflank public URL (no trailing slash). `frontend/vercel.json` sends unknown paths to `index.html` so client-side routes survive a refresh. Hobby is for non-commercial use: no ads, payments or paid work on the site.

Then put the Vercel URL in the API's `CORS_ORIGINS` and redeploy the API.

## 4. First data

Run these from your machine, with `DATABASE_URL` pointing at the **direct** Neon string (they are one-off commands, no pooler needed):

```powershell
cd backend
$env:DATABASE_URL = "postgresql+asyncpg://...direct...?ssl=require"
$env:JWT_SECRET_KEY = "unused-here-but-required-to-load-settings"
uv run python -m app.cli create-admin --email you@example.com --name You   # asks for the password
uv run python -m app.cli seed-demo
```

## 5. Keeping the demo tidy

A Northflank cron job (the Sandbox plan includes two) running daily with the API's image and variables:

```
python -m app.cli seed-demo --prune-days 7
```

It tops up the sample reservations and deletes non-admin reservations that ended more than 7 days ago, to stay far from Neon's 1 GB storage limit. Watch the storage in Neon's console.
