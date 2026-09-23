import { defineConfig, devices } from "@playwright/test";

const externalBaseURL = process.env.E2E_BASE_URL;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: 0,
  // Keep the real Python recommendation engine and remote AI within a modest load.
  workers: 2,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: externalBaseURL || "http://localhost:3100",
    actionTimeout: 15_000,
    navigationTimeout: 30_000,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    locale: "ru-RU",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
  webServer: externalBaseURL
    ? undefined
    : [
        {
          command: "uv run uvicorn api.index:app --port 8000",
          url: "http://127.0.0.1:8000/api/py/health",
          reuseExistingServer: true,
          timeout: 120_000,
          gracefulShutdown: { signal: "SIGTERM", timeout: 5_000 },
        },
        {
          command: "npx next dev -p 3100",
          url: "http://localhost:3100",
          reuseExistingServer: true,
          timeout: 120_000,
          env: { API_URL: "http://127.0.0.1:8000", NEXT_TELEMETRY_DISABLED: "1" },
          gracefulShutdown: { signal: "SIGTERM", timeout: 5_000 },
        },
      ],
});
