/**
 * Browser e2e global setup — runs as a Playwright "setup" project before all
 * other browser tests. Responsible for:
 *
 *  1. Registering the browser test user (idempotent: 400 on duplicate is OK)
 *  2. Inserting a test Note into DuckDB for the DocReader/Backlink tests
 *  3. Creating a share token for the anon share test
 *  4. Logging in via the browser UI → saving .auth.json (cookies + localStorage)
 *  5. Writing .state.json (noteId, shareToken, userId) for other tests to read
 *
 * R-3: No skips. If any step fails, the test fails loudly.
 * Security: DuckDB values passed via env vars to a temp Python file, never
 * interpolated into a shell command string (avoids command injection).
 */
import { test as setup, expect } from "@playwright/test";
import { execFileSync } from "child_process";
import * as fs from "fs";
import * as os from "os";
import * as path from "path";
import { fileURLToPath } from "url";

// __dirname equivalent in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const BACKEND = "http://localhost:9311";
const AUTH_FILE = path.join(__dirname, ".auth.json");
const STATE_FILE = path.join(__dirname, ".state.json");

// Stable, idempotent IDs — re-running the setup is safe because DuckDB uses
// ON CONFLICT DO NOTHING and registration returns 400 for duplicates.
const NOTE_ID = "browser_e2e_note_001";
const TEST_EMAIL = "broe2e@playwright-e2e.com";
const TEST_USERNAME = "broe2e_playwright";
const TEST_PASSWORD = "BrowserE2E123!";

// Python script for DuckDB note insertion.  Dynamic values (NOTE_ID, corpusId)
// are passed via environment variables — never interpolated into the script
// string — so no shell injection is possible regardless of their content.
const INSERT_NOTE_PY = `
import duckdb, os, sys

note_id   = os.environ["NOTE_ID"]
corpus_id = os.environ["CORPUS_ID"]
db_path   = os.path.expanduser("~/.stratum/meta.duckdb")

conn = duckdb.connect(db_path)
try:
    conn.execute(
        "INSERT INTO note "
        "(id, corpus_id, title, content, wikilinks, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
        "ON CONFLICT (id) DO UPDATE SET corpus_id = EXCLUDED.corpus_id",
        [
            note_id, corpus_id,
            "浏览器E2E测试笔记",
            "# E2E测试\\n这是浏览器端对端测试的内容。\\n\\n测试 [[反链测试]]。",
            '["反链测试"]',
        ],
    )
finally:
    conn.close()

print("note_ok")
`.trimStart();

setup("create test data + authenticate", async ({ page }) => {
  // ── 1. Register test user (ignore 400 if already exists) ────────────────
  const regRes = await page.request.post(`${BACKEND}/api/auth/register`, {
    data: { email: TEST_EMAIL, username: TEST_USERNAME, password: TEST_PASSWORD },
  });

  let userId: string;
  if (regRes.status() === 200) {
    const body = await regRes.json();
    userId = body.user_id;
  } else if (regRes.status() === 400) {
    // User already exists — retrieve user_id via fresh login
    const loginRes = await page.request.post(`${BACKEND}/api/auth/login`, {
      data: { email_or_username: TEST_EMAIL, password: TEST_PASSWORD },
    });
    expect(loginRes.status(), "login must succeed for existing test user").toBe(200);
    const loginBody = await loginRes.json();
    userId = (loginBody.user as { user_id: string }).user_id;
  } else {
    throw new Error(
      `Registration returned unexpected status ${regRes.status()}: ${await regRes.text()}`
    );
  }

  const corpusId = `user_${userId}`;

  // ── 2. Insert test note into DuckDB (values via env vars, not shell string) ─
  const tmpScript = path.join(os.tmpdir(), `stratum_setup_${Date.now()}.py`);
  fs.writeFileSync(tmpScript, INSERT_NOTE_PY, "utf8");
  try {
    const result = execFileSync(
      "/home/soffy/projects/stratum/.venv/bin/python3",
      [tmpScript],
      {
        env: { ...process.env, NOTE_ID, CORPUS_ID: corpusId },
        timeout: 10_000,
      }
    )
      .toString()
      .trim();
    expect(result, "DuckDB note insertion must print note_ok").toBe("note_ok");
  } finally {
    fs.unlinkSync(tmpScript);
  }

  // ── 3. Login via API to get access token for share creation ─────────────
  const tokenRes = await page.request.post(`${BACKEND}/api/auth/login`, {
    data: { email_or_username: TEST_EMAIL, password: TEST_PASSWORD },
  });
  expect(tokenRes.status(), "login for share creation").toBe(200);
  const { access_token } = await tokenRes.json() as { access_token: string };

  // ── 4. Create share for the test note (409 = already exists) ────────────
  let shareToken: string;
  const shareRes = await page.request.post(`${BACKEND}/api/share/note/${NOTE_ID}`, {
    headers: { Authorization: `Bearer ${access_token}` },
    data: { allow_anonymous: true },
  });

  if (shareRes.status() === 200) {
    const shareBody = await shareRes.json() as { token: string };
    shareToken = shareBody.token;
  } else if (shareRes.status() === 409) {
    // Already shared — retrieve from the list
    const listRes = await page.request.get(`${BACKEND}/api/shares`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    const listBody = await listRes.json() as { items: Array<{ resource_id: string; token: string }> };
    const existing = listBody.items.find((s) => s.resource_id === NOTE_ID);
    if (!existing?.token) throw new Error("Could not retrieve existing share token from list");
    shareToken = existing.token;
  } else {
    throw new Error(`Share creation failed: ${shareRes.status()} ${await shareRes.text()}`);
  }

  // ── 5. Login via browser UI (captures httpOnly refresh_token cookie) ─────
  await page.goto("http://localhost:3000/login");
  await expect(page).toHaveURL(/\/login/);

  await page.fill('input[placeholder="邮箱或用户名"]', TEST_EMAIL);
  await page.fill('input[type="password"]', TEST_PASSWORD);
  await page.click('button[type="submit"]');
  await page.waitForURL("**/search", { timeout: 30_000 });

  // ── 6. Save auth state (cookies + localStorage; CDP reads httpOnly cookies) ─
  await page.context().storageState({ path: AUTH_FILE });

  // ── 7. Write shared test state for other spec files ──────────────────────
  const state = {
    email: TEST_EMAIL,
    username: TEST_USERNAME,
    userId,
    corpusId,
    noteId: NOTE_ID,
    shareToken,
  };
  fs.writeFileSync(STATE_FILE, JSON.stringify(state, null, 2));

  console.log(
    `✓ Setup: user=${TEST_USERNAME} noteId=${NOTE_ID} shareToken=${shareToken.slice(0, 8)}…`
  );
});
