/**
 * Playwright config for BROWSER-BASED e2e tests (Task 2 / Z-2).
 *
 * Separate from playwright.config.ts (API contract tests) so the two suites
 * don't interfere. The API suite uses { request } fixture only; this one uses
 * { page } with a real Chromium browser.
 *
 * Execution order:
 *  1. webServer[0]: Stratum backend (uvicorn) on :9311
 *  2. webServer[1]: Next.js dev server on :3000 (proxied to :9311 via STRATUM_API_PORT)
 *  3. Project "setup": register test user, create note, login, save .auth.json
 *  4. Project "chromium-snap": 16 browser interaction tests using saved auth
 *  5. Project "anonymous": share/anon tests without auth cookie
 *
 * Chromium: snap install (/snap/bin/chromium ≥ 148) works on Ubuntu 26.04.
 * The snap mount-namespace warnings on stderr are harmless; --version still prints OK.
 */
import { defineConfig, devices } from "@playwright/test";
import path from "path";
import { fileURLToPath } from "url";

// __dirname equivalent in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const AUTH_FILE = path.join(__dirname, "tests/e2e/browser/.auth.json");
const BACKEND_PORT = 9311;
const BACKEND_URL = `http://localhost:${BACKEND_PORT}`;

export default defineConfig({
  testDir: "./tests/e2e/browser",
  timeout: 45000,
  retries: 1,
  workers: 1,        // DuckDB single-writer + avoid port races
  reporter: [
    ["list"],
    ["html", { open: "never", outputFolder: "playwright-report/browser" }],
  ],
  outputDir: "test-results/browser",

  use: {
    baseURL: "http://localhost:3000",
    screenshot: "only-on-failure",
    video: "off",            // ffmpeg not available on Ubuntu 26.04 (unsupported)
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
    // ── 1. Setup: creates test user + auth state ─────────────────────────
    {
      name: "setup",
      testMatch: /setup\.ts$/,
    },

    // ── 2. Main browser tests (authenticated) ────────────────────────────
    {
      name: "chromium-snap",
      use: {
        ...devices["Desktop Chrome"],
        storageState: AUTH_FILE,
      },
      dependencies: ["setup"],
      testIgnore: [/setup\.ts$/, /04-share-anon\.spec\.ts$/],
    },

    // ── 3. Anonymous tests (no auth cookie) ──────────────────────────────
    {
      name: "anonymous",
      use: { ...devices["Desktop Chrome"] },
      dependencies: ["setup"],
      testMatch: /04-share-anon\.spec\.ts$/,
    },
  ],

  webServer: [
    // Backend: Stratum uvicorn on :9311
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
    // Frontend: Next.js on :3000, proxied to Stratum backend on :9311.
    // --webpack: Turbopack spawns too many pthreads in WSL2 ("Resource
    //   temporarily unavailable"). Webpack's single-threaded compilation
    //   is slower but reliable in resource-constrained environments.
    // RAYON_NUM_THREADS=2: limit Rust thread pool just in case any dep uses rayon.
    // timeout=300s: webpack initial compilation can take ~90s.
    {
      command: `STRATUM_API_PORT=${BACKEND_PORT} RAYON_NUM_THREADS=2 pnpm next dev --webpack`,
      url: "http://localhost:3000",
      reuseExistingServer: true,
      timeout: 300_000,
      stdout: "pipe",
      stderr: "pipe",
      env: {
        STRATUM_API_PORT: String(BACKEND_PORT),
        RAYON_NUM_THREADS: "2",
      },
    },
  ],
});
