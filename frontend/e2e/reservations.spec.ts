import { expect, test } from '@playwright/test'
import { bearer, cancelAll, farDate, login, newUser, openAs, randomFreeSlot } from './helpers'

test('a user books a cell, finds it in "Mis reservas", cancels it, and the cell is free again', async ({
  browser,
  request,
}) => {
  const date = farDate()
  const user = await newUser(request, 'jugador')
  const slot = await randomFreeSlot(request, user.token, date)
  const page = await openAs(browser, user.token, `/?fecha=${date}`)

  await page.getByRole('gridcell', { name: `${slot.courtName}, ${slot.hour}, libre` }).click()
  await page.getByRole('button', { name: 'Reservar' }).click()
  await expect(page.getByRole('status').filter({ hasText: 'Reserva confirmada' })).toBeVisible()
  await expect(page.getByRole('gridcell', { name: `${slot.courtName}, ${slot.hour}, tuya` })).toBeVisible()

  // Back on the grid the same cell is "Tuya"; "Mis reservas" lists it as upcoming.
  await page.getByRole('link', { name: 'Mis reservas' }).click()
  const upcoming = page.getByRole('table', { name: 'Próximas' })
  await expect(upcoming.getByRole('row', { name: new RegExp(slot.courtName) })).toBeVisible()
  await expect(upcoming.getByText('Confirmada')).toBeVisible()

  await upcoming.getByRole('button', { name: /Cancelar la reserva/ }).click()
  const history = page.getByRole('table', { name: 'Historial' })
  await expect(history.getByText('Cancelada')).toBeVisible()
  await expect(page.getByText('No tienes reservas próximas.')).toBeVisible()

  await page.goto(`/?fecha=${date}`)
  await expect(page.getByRole('gridcell', { name: `${slot.courtName}, ${slot.hour}, libre` })).toBeVisible()
})

test('the admin sees who booked a cell and can cancel it, which frees the cell for everyone', async ({
  browser,
  request,
}) => {
  const email = process.env.E2E_ADMIN_EMAIL ?? 'admin@demo.test'
  const password = process.env.E2E_ADMIN_PASSWORD ?? 'demo-pass-123'
  const attempt = await request.post('/api/auth/login', { form: { username: email, password } })
  test.skip(!attempt.ok(), 'No admin account: create one with `python -m app.cli create-admin` or set E2E_ADMIN_EMAIL/PASSWORD')
  const adminToken = await login(request, email, password)

  const date = farDate()
  const user = await newUser(request, `jugador${Math.floor(Math.random() * 1e5)}`)
  const slot = await randomFreeSlot(request, user.token, date)
  const booked = await request.post('/api/reservations', {
    headers: bearer(user.token),
    data: { resource_id: slot.courtId, starts_at: slot.start },
  })
  expect(booked.status()).toBe(201)

  const admin = await openAs(browser, adminToken, `/admin?fecha=${date}`)
  // The admin's cell names who holds it; a regular user's would not.
  const cell = admin.getByRole('gridcell', {
    name: new RegExp(`${slot.courtName}, ${slot.hour}, ocupada, reservada por ${user.name}`),
  })
  await expect(cell).toBeVisible()
  await cell.click()
  await admin.getByRole('button', { name: 'Cancelar reserva' }).click()
  await expect(admin.getByRole('status').filter({ hasText: 'Reserva cancelada' })).toBeVisible()
  await expect(admin.getByRole('gridcell', { name: `${slot.courtName}, ${slot.hour}, libre` })).toBeVisible()

  // The user's own list now shows it as cancelled.
  const mine = await (await request.get('/api/reservations', { headers: bearer(user.token) })).json()
  expect(mine.items.map((r: { status: string }) => r.status)).toEqual(['cancelled'])
  await cancelAll(request, user.token)
})
