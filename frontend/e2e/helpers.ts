import { expect, type APIRequestContext, type Browser, type Page } from '@playwright/test'

export const PASSWORD = 'e2e-pass-12345'
const TZ = 'America/Mexico_City'

/** Registers a fresh user (so the per-user limit never gets in the way) and returns its token. */
export async function newUser(request: APIRequestContext, label: string) {
  const email = `${label}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@e2e-mail.dev`
  const register = await request.post('/api/auth/register', { data: { email, password: PASSWORD, name: label } })
  expect(register.ok()).toBeTruthy()
  return { email, name: label, token: await login(request, email, PASSWORD) }
}

export async function login(request: APIRequestContext, email: string, password: string) {
  const res = await request.post('/api/auth/login', { form: { username: email, password } })
  expect(res.ok(), `login for ${email}`).toBeTruthy()
  return (await res.json()).access_token as string
}

export const bearer = (token: string) => ({ Authorization: `Bearer ${token}` })

/** A day far enough ahead that the 12-hour cancellation window never matters. */
export const farDate = (daysAhead = 25) => new Date(Date.now() + daysAhead * 86_400_000).toISOString().slice(0, 10)

export const hourLabel = (iso: string) =>
  new Intl.DateTimeFormat('es-MX', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).format(new Date(iso))

/** A random free slot on `date`, read from the API so the test never guesses the schedule. */
export async function randomFreeSlot(request: APIRequestContext, token: string, date: string) {
  const res = await request.get(`/api/availability?date=${date}`, { headers: bearer(token) })
  const day = await res.json()
  const free = day.courts.flatMap((c: { id: string; name: string; slots: { start: string; status: string }[] }) =>
    c.slots.filter((s) => s.status === 'available').map((s) => ({ courtId: c.id, courtName: c.name, start: s.start })),
  )
  expect(free.length).toBeGreaterThan(0)
  const pick = free[Math.floor(Math.random() * free.length)]
  return { ...pick, hour: hourLabel(pick.start) } as { courtId: string; courtName: string; start: string; hour: string }
}

/** A browser tab already signed in as `token`, looking at `path`. */
export async function openAs(browser: Browser, token: string, path: string): Promise<Page> {
  const context = await browser.newContext()
  await context.addInitScript((value) => localStorage.setItem('access_token', value), token)
  const page = await context.newPage()
  await page.goto(path)
  return page
}

/** Cancels every confirmed reservation of the user so the demo database does not fill up. */
export async function cancelAll(request: APIRequestContext, token: string) {
  const mine = await request.get('/api/reservations', { headers: bearer(token) })
  const { items } = await mine.json()
  for (const r of items) {
    if (r.status === 'confirmed') await request.post(`/api/reservations/${r.id}/cancel`, { headers: bearer(token) })
  }
}
