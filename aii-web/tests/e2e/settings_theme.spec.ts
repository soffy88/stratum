/**
 * E2E tests for settings page API contracts.
 * Theme is stored in localStorage (client-side only); these tests cover the
 * backend API that the settings page Profile/Theme tabs depend on.
 *
 * Note: localStorage-based theme persistence is covered in unit tests
 * (wave9.test.tsx ThemeTab + src/lib/theme.ts). Browser-based e2e for theme
 * requires Ubuntu ≤22 due to Playwright OS support constraints.
 */
import { test, expect } from "@playwright/test";

const API = "http://localhost:9305";
const suffix = Date.now().toString(36) + "st";

let accessToken: string;

test.beforeAll(async ({ request }) => {
  await request.post(`${API}/api/auth/register`, {
    data: { email: `st_${suffix}@t.com`, username: `st_${suffix}`, password: "TestPass123!" },
  });
  const login = await request.post(`${API}/api/auth/login`, {
    data: { email_or_username: `st_${suffix}@t.com`, password: "TestPass123!" },
  });
  accessToken = (await login.json()).access_token;
});

function auth() { return { Authorization: `Bearer ${accessToken}` }; }

test.describe("Settings — profile tab API", () => {
  test("GET /api/auth/me returns username + email for Profile tab", async ({ request }) => {
    const res = await request.get(`${API}/api/auth/me`, { headers: auth() });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.username).toBe(`st_${suffix}`);
    expect(body.email).toBe(`st_${suffix}@t.com`);
    // These are the two fields rendered in the settings Profile tab
    expect(body.user_id).toBeTruthy();
  });

  test("GET /api/shares returns share list for own profile display", async ({ request }) => {
    const res = await request.get(`${API}/api/shares`, { headers: auth() });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(typeof body.total).toBe("number");
    expect(Array.isArray(body.items)).toBe(true);
  });

  test("POST /api/auth/logout clears session (settings logout action)", async ({ request }) => {
    // Fresh login to get a token we'll log out
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: `st_${suffix}@t.com`, password: "TestPass123!" },
    });
    const { access_token } = await login.json();

    const logout = await request.post(`${API}/api/auth/logout`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    // 200 or 204 both valid
    expect([200, 204]).toContain(logout.status());
  });
});
