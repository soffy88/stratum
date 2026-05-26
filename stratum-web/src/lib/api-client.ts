/**
 * HTTP REST client for Stratum API.
 * - access token in memory (XSS safe)
 * - refresh token via httpOnly cookie (auto-sent by browser)
 * - 401 auto-refresh + retry
 */

export class AuthRequiredError extends Error {
  constructor() { super("Authentication required"); }
}

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

class ApiClient {
  private accessToken: string | null = null;
  private refreshPromise: Promise<void> | null = null;

  setAccessToken(token: string | null) { this.accessToken = token; }
  getAccessToken() { return this.accessToken; }

  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const res = await this._fetch(method, path, body);

    if (res.status === 401) {
      await this._refresh();
      const retry = await this._fetch(method, path, body);
      if (retry.status === 401) throw new AuthRequiredError();
      if (!retry.ok) throw new ApiError(retry.status, await retry.text());
      return retry.json() as Promise<T>;
    }

    if (res.status === 429) throw new ApiError(429, "Rate limit exceeded");
    if (!res.ok) throw new ApiError(res.status, await res.text());
    return res.json() as Promise<T>;
  }

  private _fetch(method: string, path: string, body?: unknown) {
    const headers: Record<string, string> = { "Content-Type": "application/json" };
    if (this.accessToken) headers["Authorization"] = `Bearer ${this.accessToken}`;
    return fetch(path, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      credentials: "include",
    });
  }

  private async _refresh(): Promise<void> {
    if (this.refreshPromise) return this.refreshPromise;
    this.refreshPromise = (async () => {
      const res = await fetch("/api/auth/refresh", { method: "POST", credentials: "include" });
      if (!res.ok) throw new AuthRequiredError();
      const data = await res.json();
      this.accessToken = data.access_token;
    })();
    try { await this.refreshPromise; } finally { this.refreshPromise = null; }
  }

  get<T>(path: string) { return this.request<T>("GET", path); }
  post<T>(path: string, body?: unknown) { return this.request<T>("POST", path, body); }
  put<T>(path: string, body?: unknown) { return this.request<T>("PUT", path, body); }
  delete<T>(path: string) { return this.request<T>("DELETE", path); }
}

export const apiClient = new ApiClient();
