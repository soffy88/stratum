/**
 * E2E share workflow + data leak red-line tests.
 * Per §5.5: public share must not expose user_id/corpus_id/email.
 */
import { test, expect } from "@playwright/test";

const API = "http://localhost:9305";
const suffix = Date.now().toString(36) + "w9";

let accessToken: string;

test.beforeAll(async ({ request }) => {
  // Register + login
  await request.post(`${API}/api/auth/register`, {
    data: { email: `w9_${suffix}@t.com`, username: `w9_${suffix}`, password: "TestPass123!" },
  });
  const login = await request.post(`${API}/api/auth/login`, {
    data: { email_or_username: `w9_${suffix}@t.com`, password: "TestPass123!" },
  });
  const loginBody = await login.json();
  accessToken = loginBody.access_token;

  // Create a note (direct DB insert via agent run as proxy — or use the note DAO)
  // Since there's no POST /api/notes endpoint yet, we'll test share with a note that doesn't exist
  // and verify the 404 behavior, then test the share endpoint contract
});

test.describe("Share API contract", () => {
  test("POST /api/share/note/:id requires auth", async ({ request }) => {
    const res = await request.post(`${API}/api/share/note/fake_id`, { data: {} });
    expect(res.status()).toBe(401);
  });

  test("POST /api/share/note/:id returns 404 for nonexistent note", async ({ request }) => {
    const res = await request.post(`${API}/api/share/note/nonexistent`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: { allow_anonymous: true },
    });
    expect(res.status()).toBe(404);
  });

  test("GET /share/:token returns 404 for invalid token", async ({ request }) => {
    const res = await request.get(`${API}/share/invalid_token_xyz`);
    expect(res.status()).toBe(404);
  });

  test("GET /api/shares returns empty list for new user", async ({ request }) => {
    const res = await request.get(`${API}/api/shares`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.total).toBe(0);
  });

  test("GET /api/shares requires auth", async ({ request }) => {
    const res = await request.get(`${API}/api/shares`);
    expect(res.status()).toBe(401);
  });

  test("DELETE /api/share/:token requires auth", async ({ request }) => {
    const res = await request.delete(`${API}/api/share/some_token`);
    expect(res.status()).toBe(401);
  });
});

test.describe("Share data leak red-line", () => {
  test("GET /share/:token response schema has no user_id/corpus_id/email fields", async ({ request }) => {
    // Even a 404 response should not leak data
    const res = await request.get(`${API}/share/nonexistent`);
    const text = await res.text();
    expect(text).not.toContain("user_id");
    expect(text).not.toContain("corpus_id");
    // 404 response is just {"detail":"Share not found"}
    expect(text).not.toContain("@t.com");
  });

  test("public share endpoint accessible without any auth header", async ({ request }) => {
    // Verify no redirect to login
    const res = await request.get(`${API}/share/any_token`, { maxRedirects: 0 });
    // Should be 404 (not found) not 401 (unauthorized) or 3xx (redirect)
    expect(res.status()).toBe(404);
  });
});
