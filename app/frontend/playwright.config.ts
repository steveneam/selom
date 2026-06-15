import { defineConfig, devices } from "@playwright/test";

/**
 * E2E config for the figure-editor gesture tests. Uses the system Chrome
 * (`channel: "chrome"`) so there's no Chromium download — the box already has it.
 * The webServer boots the MSW-mock dev server on :3011 (kept off :3000/:3010 so it
 * doesn't fight a dev server you're already running) and is reused if one's up.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  reporter: [["list"]],
  use: {
    baseURL: "http://localhost:3011",
    headless: true,
    viewport: { width: 1440, height: 900 },
    trace: "retain-on-failure",
  },
  projects: [{ name: "chrome", use: { ...devices["Desktop Chrome"], channel: "chrome" } }],
  webServer: {
    command: "npm run dev:mock -- --port 3011",
    url: "http://localhost:3011",
    reuseExistingServer: true,
    timeout: 120_000,
  },
});
