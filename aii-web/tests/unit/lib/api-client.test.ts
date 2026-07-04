import { describe, it, expect, vi, beforeEach } from "vitest";
import { apiClient, AuthRequiredError, ApiError } from "@/lib/api-client";

describe("ApiClient", () => {
  beforeEach(() => {
    apiClient.setAccessToken(null);
    vi.restoreAllMocks();
  });

  it("sends Authorization header when token set", async () => {
    apiClient.setAccessToken("test-token");
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => ({ data: 1 }) });
    vi.stubGlobal("fetch", mockFetch);
    await apiClient.get("/api/test");
    expect(mockFetch.mock.calls[0]?.[1]?.headers?.Authorization).toBe("Bearer test-token");
  });

  it("does not send Authorization when no token", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => ({}) });
    vi.stubGlobal("fetch", mockFetch);
    await apiClient.get("/api/test");
    expect(mockFetch.mock.calls[0]?.[1]?.headers?.Authorization).toBeUndefined();
  });

  it("throws ApiError on 400", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 400, text: () => "bad" }));
    await expect(apiClient.get("/api/test")).rejects.toBeInstanceOf(ApiError);
  });

  it("throws ApiError with status 429 on rate limit", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 429, text: () => "rate limited" }));
    await expect(apiClient.get("/api/test")).rejects.toMatchObject({ status: 429 });
  });

  it("attempts refresh on 401 then retries", async () => {
    let callCount = 0;
    vi.stubGlobal("fetch", vi.fn().mockImplementation((url: string) => {
      if (url === "/api/auth/refresh") {
        return Promise.resolve({ ok: true, json: () => ({ access_token: "new" }) });
      }
      callCount++;
      if (callCount === 1) return Promise.resolve({ ok: false, status: 401, text: () => "" });
      return Promise.resolve({ ok: true, status: 200, json: () => ({ result: "ok" }) });
    }));
    const result = await apiClient.get<{ result: string }>("/api/test");
    expect(result.result).toBe("ok");
  });

  it("throws AuthRequiredError when refresh also fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false, status: 401, text: () => "" }));
    await expect(apiClient.get("/api/test")).rejects.toBeInstanceOf(AuthRequiredError);
  });

  it("includes credentials: include", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => ({}) });
    vi.stubGlobal("fetch", mockFetch);
    await apiClient.get("/api/test");
    expect(mockFetch.mock.calls[0]?.[1]?.credentials).toBe("include");
  });

  it("sends JSON body on post", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => ({}) });
    vi.stubGlobal("fetch", mockFetch);
    await apiClient.post("/api/test", { key: "val" });
    expect(JSON.parse(mockFetch.mock.calls[0]?.[1]?.body)).toEqual({ key: "val" });
  });

  it("setAccessToken / getAccessToken roundtrip", () => {
    apiClient.setAccessToken("abc");
    expect(apiClient.getAccessToken()).toBe("abc");
  });

  it("delete method sends DELETE request", async () => {
    const mockFetch = vi.fn().mockResolvedValue({ ok: true, status: 200, json: () => ({}) });
    vi.stubGlobal("fetch", mockFetch);
    await apiClient.delete("/api/test");
    expect(mockFetch.mock.calls[0]?.[1]?.method).toBe("DELETE");
  });
});
