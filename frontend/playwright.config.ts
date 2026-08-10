import { defineConfig } from '@playwright/test'

export default defineConfig({
  testDir: './e2e',
  timeout: 240_000,
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.QSCN_E2E_URL ?? 'http://127.0.0.1:8000',
    trace: 'retain-on-failure',
    acceptDownloads: true,
  },
})
