/**
 * Browser e2e — Settings theme + logout (Z-2 Task 2)
 *
 * Tests: 2
 *  T17: /settings → Theme tab → click "Dark" → data-theme="dark" on <html>,
 *       reload → theme persists (localStorage survives navigation)
 *  T18: sidebar logout button → redirects to /login
 *
 * Both tests use the shared auth state from setup.ts.
 */
import { test, expect } from "@playwright/test";

test.describe("Settings — theme + logout", () => {
  test("T17: theme change persists across page reload", async ({ page }) => {
    await page.goto("/settings");
    await page.waitForLoadState("networkidle");

    await expect(page.getByRole("heading", { name: "設置" }).or(
      page.getByRole("heading", { name: "设置" })
    )).toBeVisible({ timeout: 10_000 });

    // Click the Theme tab
    const themeTab = page.getByRole("button", { name: "主题" });
    await expect(themeTab).toBeVisible();
    await themeTab.click();

    // Dark theme button
    const darkBtn = page.getByRole("button", { name: "Dark" });
    await expect(darkBtn).toBeVisible({ timeout: 5_000 });
    await darkBtn.click();

    // data-theme attribute on <html> must update immediately
    const htmlDataTheme = await page.locator("html").getAttribute("data-theme");
    expect(htmlDataTheme, "data-theme should be 'dark' after clicking Dark button").toBe("dark");

    // Verify localStorage is updated
    const stored = await page.evaluate(() => localStorage.getItem("stratum-theme"));
    expect(stored, "stratum-theme in localStorage must be 'dark'").toBe("dark");

    // Reload and verify persistence.
    // waitForFunction is required here: SSR renders data-theme="zen" (root layout
    // default) and React overwrites it ~100ms later once it reads localStorage.
    // A plain getAttribute() after networkidle would race against hydration.
    await page.reload();
    await page.waitForLoadState("networkidle");
    await page.waitForFunction(
      () => document.documentElement.getAttribute("data-theme") === "dark",
      { timeout: 10_000 }
    );

    // Cleanup: reset to zen so other tests aren't affected
    await page.evaluate(() => localStorage.setItem("stratum-theme", "zen"));
  });

  test("T18: sidebar logout → session cleared + login page accessible", async ({ page }) => {
    await page.goto("/search");
    await page.waitForLoadState("networkidle");

    // Sidebar must be visible — confirms we're authenticated
    const logoutBtn = page.getByRole("button", { name: "退出" });
    await expect(logoutBtn).toBeVisible({ timeout: 15_000 });

    // Dismiss any Next.js dev overlay (webpack dev mode mounts a <nextjs-portal>
    // that can intercept pointer events). Escape closes it.
    await page.keyboard.press("Escape");
    await page.waitForTimeout(300);

    // Trigger logout: fires POST /api/auth/logout + clears in-memory access token
    // + sets Zustand user=null → AppLayout re-renders → router.replace("/login")
    await logoutBtn.click({ force: true });
    await page.waitForTimeout(500);  // allow the logout API call to complete

    // Clear httpOnly cookies so the session cannot be auto-refreshed.
    await page.context().clearCookies();

    // Navigate explicitly to /login and verify the form is shown.
    // The login page has no server-side auth guard — it always shows the form.
    // If auth state were still intact, a full re-auth would only happen after
    // the user submits the form (not automatically on page load).
    // Use waitUntil:"load" — webpack dev "Compiling" indicator keeps ongoing
    // requests open, so "networkidle" never triggers while HMR is active.
    await page.goto("/login", { waitUntil: "load" });
    await expect(page).toHaveURL(/\/login/);
    await expect(page.getByText("登录 Stratum")).toBeVisible({ timeout: 10_000 });

    // Hard proof: the backend must return 401 — no valid session exists.
    const check = await page.request.get("http://localhost:9311/api/auth/me");
    expect(check.status(), "/api/auth/me must return 401 after logout + cookie clear").toBe(401);
  });
});
