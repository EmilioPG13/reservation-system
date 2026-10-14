import type { components } from '../api/schema'
import { formatHour } from '../lib/time'

export type DayAvailability = components['schemas']['DayAvailability']
export type Slot = components['schemas']['SlotRead']

/** The five interface states from the plan, plus a slot the court simply does not offer. */
export type CellKind = 'libre' | 'ocupada' | 'no-disponible' | 'seleccionada' | 'tuya' | 'cerrada'

export const KIND_TEXT: Record<CellKind, string> = {
  libre: 'Libre',
  ocupada: 'Ocupada',
  'no-disponible': 'No disponible',
  seleccionada: 'Seleccionada',
  tuya: 'Tuya',
  cerrada: 'Cerrada',
}

export type CellModel = {
  key: string
  courtId: string
  courtName: string
  timeZone: string
  slot: Slot | null
  kind: CellKind
  /** Whether activating the cell does something (select, deselect, open "cancel"). */
  actionable: boolean
}

export type GridModel = {
  /** One start instant per column, ascending; the union of every court's slots. */
  columns: string[]
  timeZone: string
  rows: { courtId: string; courtName: string; cells: CellModel[] }[]
}

// Keyed by instant, not by string: two endpoints may spell the same UTC time differently.
export const slotKey = (courtId: string, start: string) => `${courtId}|${Date.parse(start)}`

export function kindOf(slot: Slot | null, selected: boolean): CellKind {
  if (!slot) return 'cerrada'
  if (slot.mine && slot.status === 'booked') return 'tuya'
  if (selected && slot.status === 'available') return 'seleccionada'
  switch (slot.status) {
    case 'available':
      return 'libre'
    case 'booked':
      return 'ocupada'
    default:
      return 'no-disponible'
  }
}

export function buildGrid(day: DayAvailability, selectedKey: string | null, adminView = false): GridModel {
  const starts = new Set<string>()
  for (const court of day.courts) for (const slot of court.slots) starts.add(slot.start)
  const columns = [...starts].sort((a, b) => Date.parse(a) - Date.parse(b))
  const timeZone = day.courts[0]?.timezone ?? 'America/Mexico_City'

  const rows = day.courts.map((court) => {
    const byStart = new Map(court.slots.map((s) => [s.start, s]))
    const cells = columns.map((start): CellModel => {
      const slot = byStart.get(start) ?? null
      const key = slotKey(court.id, start)
      const kind = kindOf(slot, key === selectedKey)
      const actionable =
        kind === 'libre' ||
        kind === 'seleccionada' ||
        kind === 'tuya' ||
        (adminView && kind === 'ocupada')
      return { key, courtId: court.id, courtName: court.name, timeZone: court.timezone, slot, kind, actionable }
    })
    return { courtId: court.id, courtName: court.name, cells }
  })
  return { columns, timeZone, rows }
}

/** "Cancha 2, 09:00, ocupada": what a screen reader says for a cell. */
export function cellLabel(cell: CellModel, opts: { changed?: boolean; bookedBy?: string } = {}): string {
  const hour = cell.slot ? formatHour(cell.slot.start, cell.timeZone) : ''
  const state = KIND_TEXT[cell.kind].toLowerCase()
  const parts = [cell.courtName, hour, state]
  if (opts.bookedBy) parts.push(`reservada por ${opts.bookedBy}`)
  if (opts.changed) parts.push('acaba de ser tomada')
  return parts.filter(Boolean).join(', ')
}

/** Start instants whose slot went from available to booked by someone else between two polls. */
export function newlyTaken(previous: DayAvailability | undefined, next: DayAvailability): string[] {
  if (!previous || previous.date !== next.date) return []
  const wasFree = new Set<string>()
  for (const court of previous.courts)
    for (const slot of court.slots) if (slot.status === 'available') wasFree.add(slotKey(court.id, slot.start))
  const taken: string[] = []
  for (const court of next.courts)
    for (const slot of court.slots) {
      const key = slotKey(court.id, slot.start)
      if (wasFree.has(key) && slot.status === 'booked' && !slot.mine) taken.push(key)
    }
  return taken
}

/** The first and last visible hour of a scrolled grid, for the sticky "08–13 h" guide. */
export function visibleRange(columns: string[], first: number, last: number, timeZone: string): string {
  if (columns.length === 0) return ''
  const a = Math.max(0, Math.min(first, columns.length - 1))
  const b = Math.max(a, Math.min(last, columns.length - 1))
  const hour = (i: number) => formatHour(columns[i], timeZone).slice(0, 2)
  return a === b ? `${hour(a)} h` : `${hour(a)}–${hour(b)} h`
}
