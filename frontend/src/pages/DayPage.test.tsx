import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthContext } from '../auth/context'
import { day, hourZ, slot } from '../test/fixtures'
import { DayPage } from './DayPage'

// The typed client is the only thing between the page and the network.
const get = vi.fn()
const post = vi.fn()
vi.mock('../api/client', () => ({
  api: { GET: (...args: unknown[]) => get(...args), POST: (...args: unknown[]) => post(...args) },
}))

const auth = {
  user: { id: 'u1', email: 'a@b.c', name: 'Ana', role: 'user' },
  loading: false,
  login: vi.fn(),
  register: vi.fn(),
  logout: vi.fn(),
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <AuthContext.Provider value={auth}>
        <MemoryRouter initialEntries={['/?fecha=2030-06-12']}>
          <DayPage />
        </MemoryRouter>
      </AuthContext.Provider>
    </QueryClientProvider>,
  )
}

const availabilityCalls = () => get.mock.calls.filter(([path]) => path === '/availability').length

beforeEach(() => {
  get.mockReset()
  post.mockReset()
  get.mockImplementation(async (path: string) =>
    path === '/availability'
      ? { data: day([{ id: 'c1', name: 'Cancha 1', slots: [slot(9), slot(10)] }]) }
      : { data: { items: [], total: 0, limit: 100, offset: 0 } },
  )
})

describe('DayPage booking', () => {
  it('books the selected slot and confirms it', async () => {
    const user = userEvent.setup()
    post.mockResolvedValue({ data: { id: 'r1' } })
    renderPage()
    await user.click(await screen.findByRole('gridcell', { name: 'Cancha 1, 09:00, libre' }))
    expect(screen.getByRole('gridcell', { name: 'Cancha 1, 09:00, seleccionada' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Reservar' }))
    expect(post).toHaveBeenCalledWith('/reservations', {
      body: { resource_id: 'c1', starts_at: hourZ(9) },
    })
    expect(await screen.findByRole('status')).toHaveTextContent(/Reserva confirmada: Cancha 1/)
  })

  it('turns a 409 into "ese horario acaba de ser tomado", marks the cell and refreshes the grid', async () => {
    const user = userEvent.setup()
    post.mockResolvedValue({ error: { detail: 'That slot was just taken' } })
    renderPage()
    await user.click(await screen.findByRole('gridcell', { name: 'Cancha 1, 09:00, libre' }))
    const before = availabilityCalls()
    // The next poll will show the slot booked by someone else.
    get.mockImplementation(async (path: string) =>
      path === '/availability'
        ? { data: day([{ id: 'c1', name: 'Cancha 1', slots: [slot(9, 'booked'), slot(10)] }]) }
        : { data: { items: [], total: 0, limit: 100, offset: 0 } },
    )
    await user.click(screen.getByRole('button', { name: 'Reservar' }))

    expect(await screen.findByRole('alert')).toHaveTextContent('Ese horario acaba de ser tomado')
    await waitFor(() => expect(availabilityCalls()).toBeGreaterThan(before))
    const taken = await screen.findByRole('gridcell', { name: /Cancha 1, 09:00, ocupada, acaba de ser tomada/ })
    expect(taken).toHaveTextContent('Nueva')
    // The selection is gone, so no reserve plate is left over.
    expect(screen.queryByRole('button', { name: 'Reservar' })).not.toBeInTheDocument()
  })

  it('shows other refusals in Spanish, never the English the API sends', async () => {
    const user = userEvent.setup()
    post.mockResolvedValue({ error: { detail: 'You already have the maximum of 3 active reservations' } })
    renderPage()
    await user.click(await screen.findByRole('gridcell', { name: 'Cancha 1, 10:00, libre' }))
    await user.click(screen.getByRole('button', { name: 'Reservar' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Ya tienes el máximo de 3 reservas activas.')
  })
})
