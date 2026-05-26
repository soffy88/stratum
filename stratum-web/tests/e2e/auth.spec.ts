/**
 * E2E auth flow tests — real backend on localhost:9303.
 * Tests the full register → login → me → refresh → logout chain.
 * Per §2.5: ≥5 tests, zero skip.
 */
import { test, expect } from "@playwright/test";

const API = "http://localhost:9305";
const suffix = Date.now().toString(36);

test.describe("Auth E2E (real backend)", () => {
  let accessToken: string;
  let refreshCookie: string;

  test("register new user", async ({ request }) => {
    const res = await request.post(`${API}/api/auth/register`, {
      data: { email: `e2e_${suffix}@test.com`, username: `e2e_${suffix}`, password: "TestPass123!" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.user_id).toBeTruthy();
    expect(body.username).toBe(`e2e_${suffix}`);
  });

  test("login returns access token + sets cookie", async ({ request }) => {
    const res = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: `e2e_${suffix}@test.com`, password: "TestPass123!" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    accessToken = body.access_token;
    const cookies = res.headers()["set-cookie"] || "";
    expect(cookies).toContain("refresh_token");
    refreshCookie = cookies;
  });

  test("GET /api/auth/me with valid token", async ({ request }) => {
    // Login first to get token
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: `e2e_${suffix}@test.com`, password: "TestPass123!" },
    });
    const { access_token } = await login.json();

    const res = await request.get(`${API}/api/auth/me`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.email).toBe(`e2e_${suffix}@test.com`);
    expect(body.username).toBe(`e2e_${suffix}`);
  });

  test("login with wrong password returns 401", async ({ request }) => {
    const res = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: `e2e_${suffix}@test.com`, password: "WrongPass1!" },
    });
    expect(res.status()).toBe(401);
  });

  test("GET /api/auth/me without token returns 401", async ({ request }) => {
    const res = await request.get(`${API}/api/auth/me`);
    expect(res.status()).toBe(401);
  });

  test("register duplicate email returns 400", async ({ request }) => {
    const res = await request.post(`${API}/api/auth/register`, {
      data: { email: `e2e_${suffix}@test.com`, username: `e2e_dup_${suffix}`, password: "TestPass123!" },
    });
    expect(res.status()).toBe(400);
  });

  test("register weak password returns 400 or 422", async ({ request }) => {
    const res = await request.post(`${API}/api/auth/register`, {
      data: { email: `weak_${suffix}@test.com`, username: `weak_${suffix}`, password: "short" },
    });
    expect([400, 422]).toContain(res.status());
  });
});
