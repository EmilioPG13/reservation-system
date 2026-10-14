import { expect, test } from '@playwright/test'
import { cancelAll, farDate, newUser, openAs } from './helpers'

test('two people reserve the same cell at once: one wins, the other is told it was just taken', async ({
  browser,
  request,
}) => {
  // A random court and hour per run, so repeated runs never collide.
  const date = farDate()
  const court = `Cancha ${1 + Math.floor(Math.random() * 6)}`
  const hour = String(8 + Math.floor(Math.random() * 14)).padStart(2, '0')
  const cell = `${court}, ${hour}:00, libre`

  const ana = await newUser(request, 'ana')
  const luis = await newUser(request, 'luis')
  const pages = await Promise.all([ana, luis].map((u) => openAs(browser, u.token, `/?fecha=${date}`)))
  await Promise.all(pages.map((p) => p.getByRole('grid').waitFor()))

  // Both see the cell free and both select it before either confirms.
  for (const page of pages) await page.getByRole('gridcell', { name: cell }).click()
  const reserve = pages.map((page) => page.getByRole('button', { name: 'Reservar' }))
  await Promise.all(reserve.map((button) => expect(button).toBeEnabled()))

  // The race itself: both confirm at the same moment.
  await Promise.all(reserve.map((button) => button.click()))

  const outcomes = await Promise.all(
    pages.map(async (page) => {
      const message = page
        .locator('[role=status], [role=alert]')
        .filter({ hasText: /Reserva confirmada|Ese horario acaba de ser tomado/ })
      await expect(message).toBeVisible()
      return (await message.textContent()) ?? ''
    }),
  )
  expect(outcomes.filter((m) => m.includes('Reserva confirmada'))).toHaveLength(1)
  expect(outcomes.filter((m) => m.includes('Ese horario acaba de ser tomado'))).toHaveLength(1)

  // The loser's grid refreshes: the cell is taken and marked as just changed, and no plate is left.
  const loser = outcomes[0].includes('Ese horario') ? pages[0] : pages[1]
  await expect(
    loser.getByRole('gridcell', { name: new RegExp(`${court}, ${hour}:00, ocupada, acaba de ser tomada`) }),
  ).toBeVisible()
  await expect(loser.getByRole('button', { name: 'Reservar' })).toHaveCount(0)

  const winner = outcomes[0].includes('Reserva confirmada') ? ana : luis
  await cancelAll(request, winner.token)
})
