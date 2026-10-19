/**
 * AII Notes P0 冒烟（API 契约，API-level：Ubuntu 26.04 不支持 Playwright 浏览器）。
 *
 * 约定的后端契约（后端 P0-1 / P0-2 / P0-4）：
 * - PUT /api/v1/notes/{id} 每次更新写入一条版本
 * - GET /api/v1/notes/{id}/revisions → version DESC 列表，
 *   字段：version / title / cause / author / created_at
 * - POST /api/v1/notes/{id}/revisions/{version}/restore → 恢复（写新版本）
 * - DELETE /api/v1/notes/{id} 默认软删
 * - GET /api/v1/notes/trash → 回收站列表（路由在 /notes/{id} 之前）
 * - POST /api/v1/notes/{id}/restore → 从回收站恢复
 */
import { test, expect } from "@playwright/test";

const API = "http://localhost:9305";
const suffix = Date.now().toString(36) + "n0";

let accessToken = "";
let targetId = "";
let noteId = "";
let originalContent = "";

const auth = () => ({ Authorization: `Bearer ${accessToken}` });

function asItems(body: unknown): { id: string; version?: number }[] {
  if (Array.isArray(body)) return body as { id: string; version?: number }[];
  if (body && typeof body === "object") {
    const o = body as { items?: unknown; revisions?: unknown };
    if (Array.isArray(o.items)) return o.items as { id: string; version?: number }[];
    if (Array.isArray(o.revisions)) return o.revisions as { id: string; version?: number }[];
  }
  return [];
}

test.describe("AII Notes P0 契约", () => {
  test("注册并登录", async ({ request }) => {
    const email = `n0_${suffix}@t.com`;
    await request.post(`${API}/api/auth/register`, {
      data: { email, username: `n0_${suffix}`, password: "TestPass123!" },
    });
    const login = await request.post(`${API}/api/auth/login`, {
      data: { email_or_username: email, password: "TestPass123!" },
    });
    expect(login.status()).toBe(200);
    accessToken = (await login.json()).access_token;
    expect(accessToken).toBeTruthy();
  });

  test("创建目标笔记与带 wikilink 的笔记", async ({ request }) => {
    const t = await request.post(`${API}/api/v1/notes`, {
      headers: auth(),
      data: { title: "链接目标", content_markdown: "目标正文" },
    });
    expect(t.status()).toBe(200);
    targetId = (await t.json()).note_id;
    expect(targetId).toBeTruthy();

    originalContent = `正文见 [[${targetId}]]`;
    const n = await request.post(`${API}/api/v1/notes`, {
      headers: auth(),
      data: { title: "源笔记", content_markdown: originalContent },
    });
    expect(n.status()).toBe(200);
    noteId = (await n.json()).note_id;
    expect(noteId).toBeTruthy();
  });

  test("详情正文保留 [[id]]（前端据此渲染出链）", async ({ request }) => {
    const res = await request.get(`${API}/api/v1/notes/${noteId}`, { headers: auth() });
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.content_markdown).toContain(`[[${targetId}]]`);
    // 若后端返回解析后的 wikilinks，出链目标应在其中
    if (Array.isArray(body.wikilinks)) {
      expect(body.wikilinks).toContain(targetId);
    }
  });

  test("两次更新后版本历史为 version DESC", async ({ request }) => {
    for (const text of ["第二版", "第三版"]) {
      const u = await request.put(`${API}/api/v1/notes/${noteId}`, {
        headers: auth(),
        data: { content_markdown: text },
      });
      expect(u.status()).toBe(200);
    }
    const res = await request.get(`${API}/api/v1/notes/${noteId}/revisions`, {
      headers: auth(),
    });
    expect(res.status()).toBe(200);
    const items = asItems(await res.json());
    expect(items.length).toBeGreaterThanOrEqual(2);
    for (const r of items) {
      expect(r).toHaveProperty("version");
      expect(r).toHaveProperty("title");
      expect(r).toHaveProperty("cause");
      expect(r).toHaveProperty("author");
      expect(r).toHaveProperty("created_at");
    }
    const versions = items.map((r) => r.version ?? 0);
    expect(versions).toEqual([...versions].sort((a, b) => b - a));
  });

  test("恢复到第一版后正文回到原文", async ({ request }) => {
    const list = await request.get(`${API}/api/v1/notes/${noteId}/revisions`, {
      headers: auth(),
    });
    const items = asItems(await list.json());
    const v1 = items[items.length - 1]?.version;
    expect(v1).toBeTruthy();
    const res = await request.post(
      `${API}/api/v1/notes/${noteId}/revisions/${v1}/restore`,
      { headers: auth(), data: {} },
    );
    expect(res.status()).toBe(200);
    const note = await request.get(`${API}/api/v1/notes/${noteId}`, { headers: auth() });
    expect((await note.json()).content_markdown).toBe(originalContent);
  });

  test("删除默认软删：列表消失、回收站出现", async ({ request }) => {
    const del = await request.delete(`${API}/api/v1/notes/${noteId}`, { headers: auth() });
    expect(del.status()).toBe(200);
    const list = await request.get(`${API}/api/v1/notes`, { headers: auth() });
    const ids = ((await list.json()) as { id: string }[]).map((n) => n.id);
    expect(ids).not.toContain(noteId);
    // /notes/trash 必须命中回收站路由（而非被 /notes/{id} 当成 id）
    const trash = await request.get(`${API}/api/v1/notes/trash`, { headers: auth() });
    expect(trash.status()).toBe(200);
    const tids = asItems(await trash.json()).map((n) => n.id);
    expect(tids).toContain(noteId);
  });

  test("从回收站恢复后回到列表", async ({ request }) => {
    const res = await request.post(`${API}/api/v1/notes/${noteId}/restore`, {
      headers: auth(),
      data: {},
    });
    expect(res.status()).toBe(200);
    const list = await request.get(`${API}/api/v1/notes`, { headers: auth() });
    const ids = ((await list.json()) as { id: string }[]).map((n) => n.id);
    expect(ids).toContain(noteId);
    const trash = await request.get(`${API}/api/v1/notes/trash`, { headers: auth() });
    const tids = asItems(await trash.json()).map((n) => n.id);
    expect(tids).not.toContain(noteId);
  });
});
