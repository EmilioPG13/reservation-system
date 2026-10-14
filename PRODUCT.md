# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

- **Padel player (the in-fiction user):** opens the day's grid, sees every court and time slot at once, books a free slot, checks "my reservations", cancels. Often on a phone, often in a hurry.
- **Club admin:** sees the same grid with who booked each slot, manages courts, opening hours and maintenance blackouts, cancels reservations left under a blackout.
- **Technical recruiter (who opens the live demo first):** has about a minute. Must be able to open the link, see the grid, book a cell, and understand that two people cannot take the same one.

## Product Purpose

Court Booking lets padel players reserve court time slots and lets a club run its courts. It exists as a portfolio project whose engineering point is that double bookings are impossible because a PostgreSQL exclusion constraint refuses them, not because the code checks first. Success: a visitor books a slot in seconds, and when two people race for the same one, one wins and the other is told clearly and sees the grid refresh.

## Positioning

A court grid (courts x time slots for one day, all loaded in a single API call) where the double-booking guarantee lives in the database and is visible in the interface: a taken slot is taken, and the loser of a race gets an honest "that slot was just taken".

## Operating Context

- Day view: 10 demo courts, 08:00 to 22:00, one-hour slots (140 cells a day). Opening hours and slot length are configurable per court.
- Times are stored in UTC and shown in the court's time zone (`America/Mexico_City`).
- The grid refreshes by polling every 5 to 10 seconds (TanStack Query), not in real time.
- The access token lasts 30 minutes with no refresh; a 401 sends the user back to login.
- The free-tier database can be suspended, so the first load of the demo can be slow; a loading state must be shown, not hidden.

## Capabilities and Constraints

- Frontend: Vite, React 19, TypeScript, Tailwind 4, React Router, TanStack Query, typed client generated from the API's OpenAPI (`openapi-typescript`). Already scaffolded in `frontend/`.
- Slot states from the API: `available`, `booked`, `blocked`, `past`, plus `mine: true` on the user's own bookings. Interface states: Libre, Ocupada, No disponible, Seleccionada, Tuya.
- Business rules enforced by the API: no past or out-of-hours slots, at most 3 active future reservations per user, cancellation up to 12 hours before the start. A 409 means only "slot taken"; every other refusal is a 422.
- Admin names are only ever sent to admins (`GET /admin/reservations?date=`).
- Out of the MVP: real-time updates (SSE), cell hold while confirming, payments, multiple venues, recurring bookings.
- UI copy is in Spanish; code, comments and docs are in English.
- Login is an OAuth2 form where the email travels in `username`.

## Brand Commitments

Generic product named "Court Booking": no fictional club. It is not based on any of the author's jobs. No logo or brand assets exist yet.

## Evidence on Hand

No real users, testimonials, metrics or screenshots exist. Do not fabricate any. The backend's concurrency test (20 simultaneous requests, one 201 and nineteen 409) is real and may be referenced.

## Product Principles

1. State is never carried by color alone: every cell says what it is in words.
2. The interface tells the truth about the race: a lost race is explained and the grid refreshes, never a silent failure.
3. One glance, one day: the whole day's availability is the primary object; everything else supports it.
4. The grid is usable by keyboard and screen reader as a first-class path, and on a phone without the page ever overflowing sideways.
5. Honest loading and empty states: a suspended database or an empty day is shown plainly.

## Accessibility & Inclusion

WCAG 2.2 AA, plus the grid rules fixed in the project plan: text on every state, an `aria-label` per cell ("Cancha 2, 9:00, ocupada"), a single tab stop with arrow-key movement (roving tabindex), Enter or Space to select, cells at least 44 px, and a horizontally scrolling grid container with a sticky first column and hours row so the page never overflows.
