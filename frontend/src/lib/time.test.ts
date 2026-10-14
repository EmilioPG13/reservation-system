import { describe, expect, it } from 'vitest'
import { addDays, formatHour, isIsoDate, todayIn, zonedToUtc } from './time'

describe('zonedToUtc', () => {
  it('reads wall time in the given zone, across the daylight-saving change', () => {
    expect(zonedToUtc('2030-01-15T09:00', 'America/New_York')).toBe('2030-01-15T14:00:00.000Z') // UTC-5
    expect(zonedToUtc('2030-06-12T09:00', 'America/New_York')).toBe('2030-06-12T13:00:00.000Z') // UTC-4
    expect(zonedToUtc('2030-06-12T09:00', 'America/Mexico_City')).toBe('2030-06-12T15:00:00.000Z')
  })

  it('round-trips with formatHour', () => {
    expect(formatHour(zonedToUtc('2030-06-12T21:30', 'America/Mexico_City'), 'America/Mexico_City')).toBe('21:30')
  })
})

describe('dates', () => {
  it('adds days across month ends', () => {
    expect(addDays('2030-01-31', 1)).toBe('2030-02-01')
    expect(addDays('2030-03-01', -1)).toBe('2030-02-28')
  })

  it('reads today on the wall clock of the zone, not the machine', () => {
    const instant = new Date('2030-06-12T03:00:00Z') // still June 11 in Mexico City
    expect(todayIn('America/Mexico_City', instant)).toBe('2030-06-11')
    expect(todayIn('UTC', instant)).toBe('2030-06-12')
  })

  it('validates the ?fecha= parameter', () => {
    expect(isIsoDate('2030-06-12')).toBe(true)
    expect(isIsoDate('12/06/2030')).toBe(false)
    expect(isIsoDate(null)).toBe(false)
  })
})
