import type { DayAvailability, Slot } from '../grid/model'

const TZ = 'America/Mexico_City'

/** Mexico City is UTC-6 all year, so 09:00 local is 15:00Z. */
export const hourZ = (hour: number) => `2030-06-12T${String(hour + 6).padStart(2, '0')}:00:00Z`

export function slot(hour: number, status: Slot['status'] = 'available', mine = false): Slot {
  return { start: hourZ(hour), end: hourZ(hour + 1), status, mine }
}

export function day(courts: { id: string; name: string; slots: Slot[] }[]): DayAvailability {
  return {
    date: '2030-06-12',
    courts: courts.map((c) => ({ ...c, timezone: TZ, slot_minutes: 60 })),
  }
}

/** Two courts, three hours: every interface state appears once. */
export function sampleDay(): DayAvailability {
  return day([
    { id: 'c1', name: 'Cancha 1', slots: [slot(8), slot(9, 'booked'), slot(10, 'booked', true)] },
    { id: 'c2', name: 'Cancha 2', slots: [slot(8, 'blocked'), slot(9), slot(10, 'past')] },
  ])
}
