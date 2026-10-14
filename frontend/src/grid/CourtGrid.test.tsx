import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { hourZ, sampleDay } from '../test/fixtures'
import { CourtGrid } from './CourtGrid'
import { buildGrid, slotKey } from './model'

function setup(selected: string | null = null, extra: Partial<Parameters<typeof CourtGrid>[0]> = {}) {
  const onActivate = vi.fn()
  const model = buildGrid(sampleDay(), selected)
  render(<CourtGrid model={model} changed={new Set()} onActivate={onActivate} {...extra} />)
  return { onActivate }
}

describe('CourtGrid states', () => {
  it('writes every state as a word, never color alone, and labels each cell for screen readers', () => {
    setup(slotKey('c2', hourZ(9)))
    const cell = (name: string) => screen.getByRole('gridcell', { name })
    expect(cell('Cancha 1, 08:00, libre')).toHaveTextContent('Libre')
    expect(cell('Cancha 1, 09:00, ocupada')).toHaveTextContent('Ocupada')
    expect(cell('Cancha 1, 10:00, tuya')).toHaveTextContent('Tuya')
    expect(cell('Cancha 2, 08:00, no disponible')).toHaveTextContent('No disponible')
    expect(cell('Cancha 2, 10:00, no disponible')).toHaveTextContent('No disponible')
    expect(cell('Cancha 2, 09:00, seleccionada')).toHaveTextContent('Seleccionada')
    expect(cell('Cancha 2, 09:00, seleccionada')).toHaveAttribute('aria-selected', 'true')
  })

  it('names the court on each row and the local hour on each column', () => {
    setup()
    expect(screen.getByRole('rowheader', { name: 'Cancha 2' })).toBeInTheDocument()
    expect(screen.getByRole('columnheader', { name: '09:00' })).toBeInTheDocument()
  })

  it('marks a slot someone just took, in words and in the label', () => {
    setup(null, { changed: new Set([slotKey('c1', hourZ(9))]) })
    const cell = screen.getByRole('gridcell', { name: /Cancha 1, 09:00, ocupada, acaba de ser tomada/ })
    expect(within(cell).getByText('Nueva')).toBeInTheDocument()
  })

  it('shows who booked in the admin view', () => {
    setup(null, { bookedBy: new Map([[slotKey('c1', hourZ(9)), 'Ana Pérez']]) })
    expect(screen.getByRole('gridcell', { name: /reservada por Ana Pérez/ })).toHaveTextContent('Ana Pérez')
  })
})

describe('CourtGrid keyboard', () => {
  it('has a single tab stop, on the first cell that can be acted on', () => {
    setup()
    const stops = screen.getAllByRole('gridcell').filter((c) => c.tabIndex === 0)
    expect(stops).toHaveLength(1)
    expect(stops[0]).toHaveAccessibleName('Cancha 1, 08:00, libre')
  })

  it('moves with the arrows, including onto cells that are not actionable, and the tab stop follows', async () => {
    const user = userEvent.setup()
    setup()
    await user.tab()
    expect(screen.getByRole('gridcell', { name: 'Cancha 1, 08:00, libre' })).toHaveFocus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('gridcell', { name: 'Cancha 1, 09:00, ocupada' })).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByRole('gridcell', { name: 'Cancha 2, 09:00, libre' })).toHaveFocus()
    await user.keyboard('{End}')
    expect(screen.getByRole('gridcell', { name: 'Cancha 2, 10:00, no disponible' })).toHaveFocus()
    await user.keyboard('{Home}')
    expect(screen.getByRole('gridcell', { name: 'Cancha 2, 08:00, no disponible' })).toHaveFocus()
    expect(screen.getAllByRole('gridcell').filter((c) => c.tabIndex === 0)).toHaveLength(1)
    // The edges do not wrap or throw.
    await user.keyboard('{ArrowLeft}{ArrowDown}')
    expect(screen.getByRole('gridcell', { name: 'Cancha 2, 08:00, no disponible' })).toHaveFocus()
  })

  it('activates a free cell with Enter and Space, and ignores cells that are not actionable', async () => {
    const user = userEvent.setup()
    const { onActivate } = setup()
    await user.tab()
    await user.keyboard('{Enter}')
    await user.keyboard('{ArrowDown}{ArrowRight}') // Cancha 2, 09:00, libre
    await user.keyboard(' ')
    expect(onActivate).toHaveBeenCalledTimes(2)
    await user.keyboard('{ArrowLeft}') // Cancha 2, 08:00, no disponible
    await user.keyboard('{Enter}')
    expect(onActivate).toHaveBeenCalledTimes(2)
  })

  it('does not activate a taken cell on click', async () => {
    const user = userEvent.setup()
    const { onActivate } = setup()
    await user.click(screen.getByRole('gridcell', { name: 'Cancha 1, 09:00, ocupada' }))
    expect(onActivate).not.toHaveBeenCalled()
    await user.click(screen.getByRole('gridcell', { name: 'Cancha 1, 08:00, libre' }))
    expect(onActivate).toHaveBeenCalledTimes(1)
  })
})
