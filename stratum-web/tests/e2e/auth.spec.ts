/**
 * E2E auth flow stubs.
 * Full implementation requires running backend + frontend together.
 * These are placeholder specs for Wave 6 gate.
 */
import { test, expect } from "@playwright/test";

test.describe("Auth flow", () => {
  test.skip("register → login → redirect to /search", async ({ page }) => {
    // Requires backend running on :9302
    await page.goto("/register");
    await page.fill('[placeholder="邮箱"]', "e2e@test.com");
    await page.fill('[placeholder="用户名"]', "e2euser");
    await page.fill('[placeholder*="密码"]', "TestPass123!");
    await page.click('button[type="submit"]');
    await expect(page).toHaveURL(/\/search/);
  });

  test.skip("login with wrong password shows error", async ({ page }) => {
    await page.goto("/login");
    await page.fill('[placeholder*="邮箱"]', "wrong@test.com");
    await page.fill('[placeholder="密码"]', "WrongPass1!");
    await page.click('button[type="submit"]');
    await expect(page.locator("text=登录失败")).toBeVisible();
  });

  test.skip("unauthenticated user redirected to /login", async ({ page }) => {
    await page.goto("/search");
    await expect(page).toHaveURL(/\/login/);
  });
});
