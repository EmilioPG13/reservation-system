---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Frontend (whole app): surface brief

Mode: Operate. Scope: every screen of the SPA (login/register, court grid, my reservations, admin day view, admin courts/hours/blackouts). UI copy in Spanish.

Audience and task: a padel player (often on a phone, in a hurry) finds a free slot in the day's grid and books it; a recruiter has a minute to see the grid, book a cell and understand a race for one cell has one winner; an admin sees who booked and manages courts. Product truth lives in PRODUCT.md.

Chosen direction: "Horario Gráfico" (assigned by roll, seed b6c1670f, user kept it). Raises: guide hours in the sticky hours row (visible range, recomputed on scroll); whole-hour-column snapping on horizontal scroll; state mark in a fixed cell beside the state word, and one inverted opaque plate per screen for the primary action (the whole band is ink, text and buttons in paper). Kept from the gate-board challenger as a behavior, not a look: a slot that changed since the last poll stays marked until noticed.

Unresolved: exact typeface (system stack vs a neutral grotesque loaded locally), Spanish copy for errors, how the 409 "ese horario acaba de ser tomado" notice is placed.

## Direction contract

THESIS: A day of courts read as one printed timetable page: strict rows and columns, hairline rules, data only. Refuses the sporty rounded-card, lime-accent booking app and the dashboard of cards.

OWN-WORLD: White offset-printed timetable stock, near-black ink (#141414), grey hairlines (#C9CCD1), and a single signal red (#E2001A) that owns "Tuya" and the changed-slot hold; the red outline of "Seleccionada" is the one deliberate exception, because the selection is the live state the user is acting on. A neutral grotesque in few sizes; hours and figures tabular. No shadows, no gradients, no radii beyond hairline-square corners. Cells are ruled boxes; state is a word plus a fixed-position mark (hollow = libre, filled = ocupada, ruled-through = no disponible, red filled = tuya, red outline = seleccionada).

STORY: The visitor sees the whole day at once, picks a hollow cell, confirms on one inverted plate, and understands that a filled cell is taken for good. If someone else got it first, the page says so in plain words and the cell stays marked until noticed.

FIRST VIEWPORT: Top rule with product name left and user/menu right. Under it the day line: previous/next day buttons around the date in large type. Then the grid fills the width: sticky court-name column at left, sticky hours row at top carrying the visible-range guide ("08–13 h"), 44px minimum cells, whole-hour snapping. The one inverted plate ("Reservar") appears only once a cell is selected. On a phone the same grid scrolls inside its own container and the page never overflows.

FORM: Swiss/European railway graphic timetable (Fahrplan), candidate 5 of the ordered grounded list; seed key b6c1670f.

FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
