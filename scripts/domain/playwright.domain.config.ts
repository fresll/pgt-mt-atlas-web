import { defineConfig } from '@playwright/test'
export default defineConfig({
  testDir: '.atlas-sync-domain', timeout: 90_000, expect: { timeout: 15_000 }, workers: 2,
  use: { baseURL: 'http://localhost:4175/', launchOptions: { executablePath: process.env.CHROMIUM_PATH || undefined } },
  webServer: { command: 'node e2e/static-server.mjs 4175 ""', port: 4175, reuseExistingServer: false },
})
