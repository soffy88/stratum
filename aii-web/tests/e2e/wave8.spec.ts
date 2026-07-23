/**
 * E2E tests for Wave 8 endpoints (jobs, substrates, backlinks).
 */
import { test, expect } from "@playwright/test";

const API = "http://localhost:9305";
const suffix = Date.now().toString(36) + "w8";

let accessToken: string;

test.beforeAll(async ({ request }) => {
  await request.post(`${API}/api/auth/register`, {
    data: { email: `w8_${suffix}@t.com`, username: `w8_${suffix}`, password: "TestPass123!" },
  });
  const login = await request.post(`${API}/api/auth/login`, {
    data: { email_or_username: `w8_${suffix}@t.com`, password: "TestPass123!" },
  });
  accessToken = (await login.json()).access_token;
});

function auth() { return { Authorization: `Bearer ${accessToken}` }; }

test.describe("Scheduled Jobs CRUD", () => {
  test("create + list + delete job", async ({ request }) => {
    const create = await request.post(`${API}/api/scheduled_jobs`, {
      headers: auth(),
      data: { name: "E2E Job", agent_name: "daily_digest", cron_expression: "0 9 * * *" },
    });
    expect(create.status()).toBe(200);
    const job = await create.json();
    expect(job.name).toBe("E2E Job");

    const list = await request.get(`${API}/api/scheduled_jobs`, { headers: auth() });
    expect(list.status()).toBe(200);
    const jobs = await list.json();
    expect(jobs.items.length).toBeGreaterThanOrEqual(1);

    const del = await request.delete(`${API}/api/scheduled_jobs/${job.id}`, { headers: auth() });
    expect(del.status()).toBe(200);
  });

  test("update job enabled status", async ({ request }) => {
    const create = await request.post(`${API}/api/scheduled_jobs`, {
      headers: auth(),
      data: { name: "Toggle", agent_name: "a", cron_expression: "* * * * *" },
    });
    const job = await create.json();
    const update = await request.put(`${API}/api/scheduled_jobs/${job.id}`, {
      headers: auth(),
      data: { enabled: false },
    });
    expect(update.status()).toBe(200);
    expect((await update.json()).enabled).toBe(false);
    await request.delete(`${API}/api/scheduled_jobs/${job.id}`, { headers: auth() });
  });
});

test.describe("Substrates", () => {
  test("GET /api/substrates returns list", async ({ request }) => {
    const res = await request.get(`${API}/api/substrates`, { headers: auth() });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(Array.isArray(body.items)).toBe(true);
  });

  test("GET /api/substrates/:id returns 404 for nonexistent", async ({ request }) => {
    const res = await request.get(`${API}/api/substrates/nonexistent`, { headers: auth() });
    expect(res.status()).toBe(404);
  });
});

test.describe("Notes backlinks", () => {
  test("GET /api/notes/:id/backlinks returns 404 for nonexistent", async ({ request }) => {
    const res = await request.get(`${API}/api/notes/nonexistent/backlinks`, { headers: auth() });
    expect(res.status()).toBe(404);
  });
});
