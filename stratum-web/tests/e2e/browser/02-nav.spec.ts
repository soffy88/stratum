/**
 * Browser e2e — Sidebar navigation (Z-2 Task 2)
 *
 * Tests: 4
 *  T03: sidebar "文档" link → /documents reachable
 *  T04: sidebar "AI" link → /ai reachable
 *  T05: sidebar "任务" link → /jobs reachable
 *  T06: sidebar "设置" link → /settings reachable
 *
 * All tests use the shared auth state from setup.ts (refresh_token cookie).
 */
import { test, expect } from "@playwright/test";

test.describe("Sidebar navigation", () => {
  test.beforeEach(async ({ page }) => {
    // Start from /search (the post-login landing page)
    await page.goto("/search");
    await page.waitForLoadState("networkidle");
    // Sidebar must be visible before clicking
    await expect(page.getByRole("navigation")).toBeVisible({ timeout: 15_000 });
  });

  test("T03: sidebar 文档 → navigates to /documents", async ({ page }) => {
    await page.getByRole("link", { name: "文档" }).click();
    await expect(page).toHaveURL(/\/documents/, { timeout: 10_000 });
    // Page heading should say 文档
    await expect(page.getByRole("heading", { name: "文档" })).toBeVisible();
  });

  test("T04: sidebar AI → navigates to /ai", async ({ page }) => {
    await page.getByRole("link", { name: "AI" }).click();
    await expect(page).toHaveURL(/\/ai/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "AI 助手" })).toBeVisible();
  });

  test("T05: sidebar 任务 → navigates to /jobs", async ({ page }) => {
    await page.getByRole("link", { name: "任务" }).click();
    await expect(page).toHaveURL(/\/jobs/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "定时任务" })).toBeVisible();
  });

  test("T06: sidebar 设置 → navigates to /settings", async ({ page }) => {
    await page.getByRole("link", { name: "设置" }).click();
    await expect(page).toHaveURL(/\/settings/, { timeout: 10_000 });
    await expect(page.getByRole("heading", { name: "设置" })).toBeVisible();
  });
});
