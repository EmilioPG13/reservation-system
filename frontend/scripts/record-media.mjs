// Records the two README GIFs against a running stack (API on :8000, `npm run dev` on :5173).
//   FFMPEG=/path/to/ffmpeg node scripts/record-media.mjs
// Output: ../media/race.gif (two tabs, one wins) and ../media/grid.gif (a keyboard walkthrough).
// It creates its own users and bookings far ahead and cancels them afterwards.
import { chromium } from '@playwright/test'
import { spawnSync } from 'node:child_process'
import { mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

const BASE = process.env.E2E_BASE_URL ?? 'http://localhost:5173'
const FFMPEG = process.env.FFMPEG ?? 'ffmpeg'
const OUT = new URL('../../media/', import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, '$1')
const PASSWORD = 'media-pass-12345'
const wait = (page, ms) => page.waitForTimeout(ms)

mkdirSync(OUT, { recursive: true })
const work = mkdtempSync(join(tmpdir(), 'court-media-'))
const browser = await chromium.launch()
const api = (await browser.newContext({ baseURL: BASE })).request

async function newUser(name) {
  const email = `${name.toLowerCase()}-${Date.now()}-${Math.floor(Math.random() * 1e6)}@e2e-mail.dev`
  await api.post('/api/auth/register', { data: { email, password: PASSWORD, name } })
  const res = await api.post('/api/auth/login', { form: { username: email, password: PASSWORD } })
  return { name, token: (await res.json()).access_token }
}
const auth = (u) => ({ Authorization: `Bearer ${u.token}` })

async function cancelAll(user) {
  const { items } = await (await api.get('/api/reservations', { headers: auth(user) })).json()
  for (const r of items) if (r.status === 'confirmed') await api.post(`/api/reservations/${r.id}/cancel`, { headers: auth(user) })
}

// The video shows no mouse, so draw one.
const CURSOR = () => {
  const dot = document.createElement('div')
  dot.style.cssText =
    'position:fixed;z-index:99999;width:18px;height:18px;margin:-9px 0 0 -9px;border:2px solid #fff;background:#d90018;border-radius:50%;pointer-events:none;left:-50px;top:-50px;box-shadow:0 0 0 1px #141414'
  addEventListener('DOMContentLoaded', () => document.body.appendChild(dot))
  addEventListener('mousemove', (e) => {
    dot.style.left = e.clientX + 'px'
    dot.style.top = e.clientY + 'px'
  })
}

async function record(user, size, path) {
  const context = await browser.newContext({
    baseURL: BASE,
    viewport: size,
    recordVideo: { dir: work, size },
    locale: 'es-MX',
    timezoneId: 'America/Mexico_City',
  })
  await context.addInitScript((t) => localStorage.setItem('access_token', t), user.token)
  await context.addInitScript(CURSOR)
  const page = await context.newPage()
  await page.goto(path)
  await page.getByRole('grid').waitFor()
  return { context, page }
}

async function finish(recorders) {
  const files = []
  for (const { context, page } of recorders) {
    const video = page.video()
    await context.close()
    files.push(await video.path())
  }
  return files
}

function gif(inputs, filter, out) {
  const args = ['-y', ...inputs.flatMap((f) => ['-i', f]), '-filter_complex', filter, '-map', '[v]', out]
  const r = spawnSync(FFMPEG, args, { stdio: 'pipe' })
  if (r.status !== 0) throw new Error(String(r.stderr).slice(-600))
}
const PALETTE = 'split[a][b];[a]palettegen=max_colors=48:stats_mode=diff[p];[b][p]paletteuse=dither=none[v]'

const date = new Date(Date.now() + 26 * 86_400_000).toISOString().slice(0, 10)
const users = []
try {
  // --- race.gif: two tabs, the same cell, one wins -------------------------------------------
  const [ana, luis] = [await newUser('Ana'), await newUser('Luis')]
  users.push(ana, luis)
  const size = { width: 640, height: 500 }
  const tabs = [await record(ana, size, `/?fecha=${date}`), await record(luis, size, `/?fecha=${date}`)]
  const cell = 'Cancha 1, 11:00, libre'
  for (const { page } of tabs) await wait(page, 900)
  for (const { page } of tabs) await page.getByRole('gridcell', { name: cell }).click()
  await wait(tabs[0].page, 1600)
  const buttons = tabs.map(({ page }) => page.getByRole('button', { name: 'Reservar' }))
  await Promise.all(buttons.map((b) => b.hover()))
  await wait(tabs[0].page, 700)
  await Promise.all(buttons.map((b) => b.click()))
  await wait(tabs[0].page, 3800)
  const raceFiles = await finish(tabs)
  gif(raceFiles, `[0:v][1:v]hstack=inputs=2,fps=8,scale=1100:-1:flags=lanczos,${PALETTE}`, join(OUT, 'race.gif'))

  // --- grid.gif: a user with a booking of their own, the keyboard, and the day buttons -----------
  const [maria, pablo] = [await newUser('Maria'), await newUser('Pablo')]
  users.push(maria, pablo)
  const slots = (await (await api.get(`/api/availability?date=${date}`, { headers: auth(maria) })).json()).courts
  const book = async (u, court, index) =>
    api.post('/api/reservations', { headers: auth(u), data: { resource_id: slots[court].id, starts_at: slots[court].slots[index].start } })
  for (const [u, court, index] of [[pablo, 0, 1], [pablo, 0, 2], [pablo, 1, 6], [maria, 2, 4], [maria, 3, 9], [pablo, 4, 3]]) await book(u, court, index)
  const walk = await record(maria, { width: 1000, height: 640 }, `/?fecha=${date}`)
  const { page } = walk
  await wait(page, 1500)
  await page.getByRole('gridcell', { name: /Cancha 1, 08:00, libre/ }).click()
  for (const key of ['ArrowRight', 'ArrowRight', 'ArrowRight', 'ArrowDown', 'ArrowDown', 'ArrowRight']) {
    await page.keyboard.press(key)
    await wait(page, 450)
  }
  await page.keyboard.press('Enter')
  await wait(page, 1600)
  await page.keyboard.press('Enter')
  await wait(page, 700)
  await page.getByRole('button', { name: 'Día siguiente' }).click()
  await wait(page, 1300)
  await page.getByRole('button', { name: 'Día anterior' }).click()
  await wait(page, 1500)
  const [walkFile] = await finish([walk])
  gif([walkFile], `[0:v]fps=8,scale=900:-1:flags=lanczos,${PALETTE}`, join(OUT, 'grid.gif'))
  console.log('wrote', OUT)
} finally {
  for (const u of users) await cancelAll(u).catch(() => {})
  await browser.close()
  rmSync(work, { recursive: true, force: true })
}
