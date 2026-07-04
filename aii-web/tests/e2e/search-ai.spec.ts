/**
 * E2E tests for search + AI agent endpoints (real backend on :9305).
 */
import { test, expect } from "@playwright/test";

const API = "http://localhost:9305";
const suffix = Date.now().toString(36) + "w7";

let accessToken: string;

test.beforeAll(async ({ request }) => {
  await request.post(`${API}/api/auth/register`, {
    data: { email: `w7_${suffix}@t.com`, username: `w7_${suffix}`, password: "TestPass123!" },
  });
  const login = await request.post(`${API}/api/auth/login`, {
    data: { email_or_username: `w7_${suffix}@t.com`, password: "TestPass123!" },
  });
  const body = await login.json();
  accessToken = body.access_token;
});

test.describe("Search API", () => {
  test("POST /api/search returns results array", async ({ request }) => {
    const res = await request.post(`${API}/api/search`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: { query: "test", top_k: 5 },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.query_used).toBe("test");
    expect(Array.isArray(body.results)).toBe(true);
  });

  test("POST /api/search without auth returns 401", async ({ request }) => {
    const res = await request.post(`${API}/api/search`, {
      data: { query: "test" },
    });
    expect(res.status()).toBe(401);
  });
});

test.describe("Agent API", () => {
  test("POST /api/agents/reading_companion/run returns pending", async ({ request }) => {
    const res = await request.post(`${API}/api/agents/reading_companion/run`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      data: { params: { query: "What is machine learning?" } },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.agent_run.status).toBe("pending");
    expect(body.agent_run.agent_name).toBe("reading_companion");
  });

  test("GET /api/agents/runs returns list", async ({ request }) => {
    const res = await request.get(`${API}/api/agents/runs`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.items)).toBe(true);
    expect(body.total).toBeGreaterThanOrEqual(0);
  });

  test("GET /api/agents/runs without auth returns 401", async ({ request }) => {
    const res = await request.get(`${API}/api/agents/runs`);
    expect(res.status()).toBe(401);
  });
});
