/**
 * Browser e2e — Share anonymous access + data-leak red-line (Z-2 Task 2)
 *
 * Tests: 2  (run in "anonymous" project: no auth cookies)
 *  T15: anonymous browser visits /share/:token → sees note title + content,
 *       NO user_id / corpus_id / email in the page HTML
 *  T16: invalid share token → /share/invalid → shows "分享未找到" (404 UI)
 *
 * These tests run WITHOUT storageState (anonymous project in browser config).
 */
import { test, expect } from "@playwright/test";
import * as fs from "fs";
import * as path from "path";
import { fileURLToPath } from "url";

// __dirname equivalent in ESM
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

interface TestState { shareToken: string; username: string }
const STATE_FILE = path.join(__dirname, ".state.json");
function getState(): TestState {
  return JSON.parse(fs.readFileSync(STATE_FILE, "utf8")) as TestState;
}

test.describe("Share — anonymous access", () => {
  test("T15: /share/:token — anonymous browser sees note, no data leak", async ({ page }) => {
    const { shareToken, username } = getState();

    await page.goto(`/share/${shareToken}`);
    await page.waitForLoadState("networkidle");

    // Note title must be visible to anonymous user
    await expect(page.getByRole("heading", { name: "浏览器E2E测试笔记" })).toBeVisible({
      timeout: 20_000,
    });

    // Note content renders inside the .prose div.
    // getByText("E2E测试") would also match the title h1 (strict-mode violation),
    // so target the prose content area specifically.
    await expect(page.locator(".prose").getByText("E2E测试")).toBeVisible();

    // shared_by_username shows in header (by design — this is public data)
    await expect(page.getByText(username)).toBeVisible();

    // Red-line: no user_id / corpus_id / email in page HTML
    const html = await page.content();
    expect(html, "user_id must not appear in share page HTML").not.toContain("user_id");
    expect(html, "corpus_id must not appear in share page HTML").not.toContain("corpus_id");
    expect(html, "email must not appear in share page HTML").not.toContain("@playwright-e2e.com");
  });

  test("T16: /share/invalid_token → shows 分享未找到 UI (404 state)", async ({ page }) => {
    await page.goto("/share/invalid_browser_e2e_token_xyz");
    await page.waitForLoadState("networkidle");

    // The ShareNotFound component renders
    await expect(page.getByText("分享未找到")).toBeVisible({ timeout: 10_000 });

    // No redirect to /login (share pages are public)
    await expect(page).not.toHaveURL(/\/login/);
  });
});
