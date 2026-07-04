/**
 * Browser e2e — Auth flow (Z-2 Task 2)
 *
 * Tests: 2
 *  T01: register new user → form submit → redirect /search
 *  T02: login existing user → form submit → redirect /search
 *
 * These tests do NOT use storageState (they exercise the login form itself).
 * Each test uses a unique email/username to avoid 400 conflicts.
 */
import { test, expect } from "@playwright/test";

// Override storageState for this file — we want a clean (anonymous) context
// so the login/register forms are actually shown.
test.use({ storageState: { cookies: [], origins: [] } });

const BACKEND = "http://localhost:9311";
const ts = Date.now().toString(36);

test.describe("Auth — browser UI flow", () => {
  test("T01: register new user via form → redirects to /search", async ({ page }) => {
    const email = `ui_reg_${ts}@playwright-e2e.com`;
    const username = `ui_reg_${ts}`;
    const password = "RegisterUI123!";

    await page.goto("/register");
    await expect(page).toHaveURL(/\/register/);
    await expect(page.getByText("注册 Stratum")).toBeVisible();

    // Fill registration form
    await page.fill('input[placeholder="邮箱"]', email);
    await page.fill('input[placeholder="用户名"]', username);
    await page.fill('input[placeholder="密码 (至少 10 字符)"]', password);

    // Submit
    await page.click('button[type="submit"]');

    // After register the form also calls login → redirect to /search
    await page.waitForURL("**/search", { timeout: 25_000 });
    await expect(page).toHaveURL(/\/search/);

    // Sidebar should show username
    await expect(page.getByText(username)).toBeVisible({ timeout: 10_000 });
  });

  test("T02: login existing user via form → redirects to /search", async ({ page }) => {
    // Create a fresh user via API so this test is self-contained
    const email = `ui_login_${ts}@playwright-e2e.com`;
    const username = `ui_login_${ts}`;
    const password = "LoginUI456789!";

    await page.request.post(`${BACKEND}/api/auth/register`, {
      data: { email, username, password },
    });

    await page.goto("/login");
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText("登录 Stratum")).toBeVisible();

    await page.fill('input[placeholder="邮箱或用户名"]', email);
    await page.fill('input[type="password"]', password);
    await page.click('button[type="submit"]');

    await page.waitForURL("**/search", { timeout: 25_000 });
    await expect(page).toHaveURL(/\/search/);

    // Username appears in sidebar — confirms user object loaded
    await expect(page.getByText(username)).toBeVisible({ timeout: 10_000 });
  });
});
