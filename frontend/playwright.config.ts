import { defineConfig } from '@playwright/test'

// The end-to-end test needs the whole stack running: Postgres, the API on :8000 and `npm run dev`
// (the dev server proxies /api). Point E2E_BASE_URL elsewhere to test a deployed copy.
export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    locale: 'es-MX',
    timezoneId: 'America/Mexico_City',
    video: 'on', // the README's two-tab GIF is cut from this recording
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { browserName: 'chromium' } }],
})
