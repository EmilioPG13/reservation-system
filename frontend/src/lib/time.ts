export const DEFAULT_TIMEZONE = 'America/Mexico_City'

/** Today's calendar date (YYYY-MM-DD) as read on a wall clock in `timeZone`. */
export function todayIn(timeZone: string, now: Date = new Date()): string {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(now)
}

export function addDays(isoDate: string, days: number): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  const next = new Date(Date.UTC(y, m - 1, d + days))
  return next.toISOString().slice(0, 10)
}

export function isIsoDate(value: string | null): value is string {
  return value !== null && /^\d{4}-\d{2}-\d{2}$/.test(value) && !Number.isNaN(Date.parse(value))
}

/** "09:00" in the court's zone; the API sends instants in UTC. */
export function formatHour(instant: string, timeZone: string): string {
  return new Intl.DateTimeFormat('es-MX', {
    timeZone,
    hour: '2-digit',
    minute: '2-digit',
    hourCycle: 'h23',
  }).format(new Date(instant))
}

/** "jueves 15 de octubre" for a calendar date (no zone: it is already a wall date). */
export function formatDay(isoDate: string): string {
  const [y, m, d] = isoDate.split('-').map(Number)
  return new Intl.DateTimeFormat('es-MX', {
    timeZone: 'UTC',
    weekday: 'long',
    day: 'numeric',
    month: 'long',
  }).format(new Date(Date.UTC(y, m - 1, d)))
}

/** "jue 15 oct, 09:00–10:00" for a reservation. */
export function formatSlot(start: string, end: string, timeZone: string): string {
  const day = new Intl.DateTimeFormat('es-MX', {
    timeZone,
    weekday: 'short',
    day: 'numeric',
    month: 'short',
  }).format(new Date(start))
  return `${day}, ${formatHour(start, timeZone)}–${formatHour(end, timeZone)}`
}

function offsetMs(utcMs: number, timeZone: string): number {
  const parts = new Intl.DateTimeFormat('en-US', {
    timeZone,
    hourCycle: 'h23',
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).formatToParts(new Date(utcMs))
  const get = (type: string) => Number(parts.find((p) => p.type === type)?.value)
  const asIfUtc = Date.UTC(get('year'), get('month') - 1, get('day'), get('hour'), get('minute'), get('second'))
  return asIfUtc - Math.floor(utcMs / 1000) * 1000
}

/** Reads a `datetime-local` value ("2030-06-12T09:00") as wall time in `timeZone`; returns a UTC ISO instant. */
export function zonedToUtc(local: string, timeZone: string): string {
  const [date, time] = local.split('T')
  const [y, m, d] = date.split('-').map(Number)
  const [hh, mm] = time.split(':').map(Number)
  const wall = Date.UTC(y, m - 1, d, hh, mm)
  // Two passes: the offset at the guess can differ from the offset at the answer around a DST change.
  const first = wall - offsetMs(wall, timeZone)
  return new Date(wall - offsetMs(first, timeZone)).toISOString()
}
