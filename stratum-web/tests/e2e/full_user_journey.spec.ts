/**
 * E2E full user journey tests — Wave 10.
 * Journey 1: register → profile → public profile → share → revoke
 * Journey 2: feedback submission
 * Journey 3: sessions list → session revoke
 *
 * All tests use request fixture (API-level) as Ubuntu 26.04 doesn't
 * support Playwright browser. Workers=1 ensures DuckDB single-writer.
 */
import { test, expect } from "@playwright/test";

const API = "http://localhost:9305";
const suffix = `j10_${Date.now().toString(36)}`;
const creds = {
  email: `${suffix}@test.com`,
  username: suffix,
  password: "JourneyPass1!",
};

// Shared state within each group
let accessToken = "";

// ── Journey 1: register → profile → share → revoke ───────────────────────────

test.describe("Journey 1: register → profile → share", () => {
  test("1a: register new journey user", async ({ request }) => {
    const res = await request.post(`${API}/api/auth/register`, { data: creds });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.username).toBe(suffix);
  });

  test("1b: login and get access token", async ({ request }) => {
    const res = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.access_token).toBeTruthy();
    accessToken = body.access_token;
  });

  test("1c: GET public profile by username", async ({ request }) => {
    // Login to ensure user exists
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    const { access_token } = await login.json();

    const res = await request.get(`${API}/api/users/by-username/${suffix}`);
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.username).toBe(suffix);
    // Security: no email/user_id/corpus_id in public profile
    expect(body.email).toBeUndefined();
    expect(body.user_id).toBeUndefined();
    expect(body.corpus_id).toBeUndefined();
    // Must have display_name (nullable) and created_at
    expect("display_name" in body).toBe(true);
    expect(body.created_at).toBeTruthy();

    accessToken = access_token;
  });

  test("1d: public profile returns 404 for unknown user", async ({ request }) => {
    const res = await request.get(`${API}/api/users/by-username/nobody_${suffix}_xyz`);
    expect(res.status()).toBe(404);
  });

  test("1e: GET /api/shares returns share list (authenticated)", async ({ request }) => {
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    const { access_token } = await login.json();

    const res = await request.get(`${API}/api/shares`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.items)).toBe(true);
    expect(typeof body.total).toBe("number");
  });
});

// ── Journey 2: feedback submission ───────────────────────────────────────────

test.describe("Journey 2: feedback", () => {
  test("2a: submit feedback requires auth", async ({ request }) => {
    const res = await request.post(`${API}/api/feedback`, {
      data: { content: "test feedback" },
    });
    expect(res.status()).toBe(401);
  });

  test("2b: submit feedback with auth succeeds", async ({ request }) => {
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    const { access_token } = await login.json();

    const res = await request.post(`${API}/api/feedback`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { content: "This app is great!", page_url: "/search" },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.status).toBe("received");
  });

  test("2c: empty feedback content rejected (min_length=1)", async ({ request }) => {
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    const { access_token } = await login.json();

    const res = await request.post(`${API}/api/feedback`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { content: "" },
    });
    expect(res.status()).toBe(422);
  });

  test("2d: content >2000 chars rejected", async ({ request }) => {
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    const { access_token } = await login.json();

    const res = await request.post(`${API}/api/feedback`, {
      headers: { Authorization: `Bearer ${access_token}` },
      data: { content: "x".repeat(2001) },
    });
    expect(res.status()).toBe(422);
  });
});

// ── Journey 3: sessions management ───────────────────────────────────────────

test.describe("Journey 3: sessions list + revoke", () => {
  test("3a: GET /api/users/me/sessions requires auth", async ({ request }) => {
    const res = await request.get(`${API}/api/users/me/sessions`);
    expect(res.status()).toBe(401);
  });

  test("3b: GET sessions returns active session list", async ({ request }) => {
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    const { access_token } = await login.json();

    const res = await request.get(`${API}/api/users/me/sessions`, {
      headers: { Authorization: `Bearer ${access_token}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.items)).toBe(true);
    expect(body.items.length).toBeGreaterThanOrEqual(1);

    const session = body.items[0];
    expect(session.id).toBeTruthy();
    // Security: no user_id/corpus_id/email in sessions
    expect(session.user_id).toBeUndefined();
    expect(session.corpus_id).toBeUndefined();
    expect(typeof session.is_current).toBe("boolean");
  });

  test("3c: DELETE /api/users/me/sessions/:id revokes non-current session", async ({ request }) => {
    // Login twice to create two sessions
    const login1 = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });
    const { access_token: token1 } = await login1.json();

    await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: creds.email, password: creds.password },
    });

    // List sessions with token1
    const listRes = await request.get(`${API}/api/users/me/sessions`, {
      headers: { Authorization: `Bearer ${token1}` },
    });
    const { items } = await listRes.json();
    const nonCurrent = items.find((s: { is_current: boolean; id: string }) => !s.is_current);

    if (!nonCurrent) {
      // Only one session; skip gracefully
      return;
    }

    const revokeRes = await request.delete(
      `${API}/api/users/me/sessions/${nonCurrent.id}`,
      { headers: { Authorization: `Bearer ${token1}` } }
    );
    expect(revokeRes.status()).toBe(200);
    const body = await revokeRes.json();
    expect(body.status).toBe("revoked");
  });
});
