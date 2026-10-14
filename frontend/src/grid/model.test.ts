import { describe, expect, it } from 'vitest'
import { day, hourZ, sampleDay, slot } from '../test/fixtures'
import { buildGrid, cellLabel, kindOf, newlyTaken, slotKey, visibleRange } from './model'

describe('kindOf', () => {
  it('maps every API state to its interface state', () => {
    expect(kindOf(slot(9), false)).toBe('libre')
    expect(kindOf(slot(9, 'booked'), false)).toBe('ocupada')
    expect(kindOf(slot(9, 'blocked'), false)).toBe('no-disponible')
    expect(kindOf(slot(9, 'past'), false)).toBe('no-disponible')
    expect(kindOf(slot(9, 'booked', true), false)).toBe('tuya')
    expect(kindOf(slot(9), true)).toBe('seleccionada')
    expect(kindOf(null, false)).toBe('cerrada')
  })

  it('does not show a slot as selected once someone else has taken it', () => {
    expect(kindOf(slot(9, 'booked'), true)).toBe('ocupada')
  })
})

describe('buildGrid', () => {
  it('uses the union of every court\'s hours as columns and marks missing slots closed', () => {
    const model = buildGrid(
      day([
        { id: 'a', name: 'A', slots: [slot(8), slot(9)] },
        { id: 'b', name: 'B', slots: [slot(9), slot(10)] },
      ]),
      null,
    )
    expect(model.columns).toEqual([hourZ(8), hourZ(9), hourZ(10)])
    expect(model.rows[0].cells.map((c) => c.kind)).toEqual(['libre', 'libre', 'cerrada'])
    expect(model.rows[1].cells.map((c) => c.kind)).toEqual(['cerrada', 'libre', 'libre'])
  })

  it('only lets people act on free and own cells, and admins on booked ones too', () => {
    const user = buildGrid(sampleDay(), null).rows.flatMap((r) => r.cells)
    expect(user.filter((c) => c.actionable).map((c) => c.kind)).toEqual(['libre', 'tuya', 'libre'])
    const admin = buildGrid(sampleDay(), null, true).rows.flatMap((r) => r.cells)
    expect(admin.filter((c) => c.actionable).map((c) => c.kind)).toContain('ocupada')
  })

  it('marks the selected key', () => {
    const model = buildGrid(sampleDay(), slotKey('c2', hourZ(9)))
    expect(model.rows[1].cells[1].kind).toBe('seleccionada')
  })
})

describe('cellLabel', () => {
  it('says court, local hour and state', () => {
    const cell = buildGrid(sampleDay(), null).rows[0].cells[1]
    expect(cellLabel(cell)).toBe('Cancha 1, 09:00, ocupada')
  })

  it('adds who booked it for the admin and that it was just taken', () => {
    const cell = buildGrid(sampleDay(), null).rows[0].cells[1]
    expect(cellLabel(cell, { bookedBy: 'Ana', changed: true })).toBe(
      'Cancha 1, 09:00, ocupada, reservada por Ana, acaba de ser tomada',
    )
  })
})

describe('newlyTaken', () => {
  it('reports slots that went from free to booked by someone else', () => {
    const before = day([{ id: 'c1', name: 'C1', slots: [slot(8), slot(9), slot(10)] }])
    const after = day([
      { id: 'c1', name: 'C1', slots: [slot(8, 'booked'), slot(9, 'booked', true), slot(10)] },
    ])
    expect(newlyTaken(before, after)).toEqual([slotKey('c1', hourZ(8))])
  })

  it('reports nothing on the first load or when the day changed', () => {
    expect(newlyTaken(undefined, sampleDay())).toEqual([])
    expect(newlyTaken({ ...sampleDay(), date: '2030-06-11' }, sampleDay())).toEqual([])
  })
})

describe('visibleRange', () => {
  const columns = [8, 9, 10, 11, 12, 13].map(hourZ)
  it('names the first and last hour in view', () => {
    expect(visibleRange(columns, 0, 3, 'America/Mexico_City')).toBe('08–11 h')
    expect(visibleRange(columns, 4, 99, 'America/Mexico_City')).toBe('12–13 h')
    expect(visibleRange(columns, 2, 2, 'America/Mexico_City')).toBe('10 h')
  })
})
