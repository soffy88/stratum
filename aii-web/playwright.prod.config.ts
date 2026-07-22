/**
 * Playwright config for PRODUCTION BUILD e2e tests.
 *
 * Uses `next build` + `next start` instead of `next dev`.
 * Purpose: verify that flaky tests (T02/T13/T18) pass reliably in prod mode.
 */
import { defineConfig, devices } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const AUTH_FILE = path.join(__dirname, "tests/e2e/browser/.auth.json");
const BACKEND_PORT = 9311;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

export default defineConfig({
  testDir: "./tests/e2e/browser",
  timeout: 45000,
  retries: 0,         // No retries — we want to see true flakiness
  workers: 1,
  reporter: [["list"]],
  outputDir: "test-results/browser-prod",

  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
    video: "off",
    trace: "retain-on-failure",
    launchOptions: {
      executablePath: "/snap/bin/chromium",
      args: [
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-dev-shm-usage",
        "--disable-gpu",
      ],
    },
  },

  projects: [
    {
      name: "setup",
      testMatch: /setup\.ts$/,
    },
    {
      name: "chromium-prod",
      use: { ...devices["Desktop Chrome"], storageState: AUTH_FILE },
      dependencies: ["setup"],
      testIgnore: [/setup\.ts$/, /04-share-anon\.spec\.ts$/],
    },
    {
      name: "anonymous",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
      testMatch: /04-share-anon\.spec\.ts$/,
    },
  ],

  webServer: [
    {
      command: [
        "PYTHONPATH=/home/soffy/projects/stratum/src",
        "/home/soffy/projects/stratum/.venv/bin/uvicorn",
        "stratum.http_api.app:app",
        `--port ${BACKEND_PORT}`,
        "--host 127.0.0.1",
      ].join(" "),
      url: `${BACKEND_URL}/health`,
      reuseExistingServer: true,
      timeout: 30000,
      stdout: "pipe",
      stderr: "pipe",
    },
    {
      command: "pnpm next start --port 3000",
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 30000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        STRATUM_API_PORT: String(BACKEND_PORT),
        STRATUM_API_INTERNAL_URL: BACKEND_URL,
      },
    },
  ],
});
