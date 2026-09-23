// Конфигурация проверок без записи артефактов за пределами docs/.
// После установки зависимостей: npm run e2e -- --config=docs/playwright.production.config.ts
import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "../e2e",
  fullyParallel: true,
  forbidOnly: true,
  retries: 0,
  workers: 2,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  outputDir: "./evidence/e2e-results",
  reporter: [["list"], ["json", { outputFile: "./evidence/e2e-results.json" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL || "https://career-quest-bay.vercel.app",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    // Трассы сетевых запросов могут содержать Bearer-токен.
    trace: "off",
    screenshot: "off",
    locale: "ru-RU",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
