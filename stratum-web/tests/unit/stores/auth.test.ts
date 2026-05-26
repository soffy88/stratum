import { describe, it, expect, vi, beforeEach } from "vitest";
import { useAuthStore } from "@/stores/auth";
import { apiClient } from "@/lib/api-client";

vi.mock("@/lib/api-client", () => ({
  apiClient: {
    post: vi.fn(),
    get: vi.fn(),
    setAccessToken: vi.fn(),
  },
  AuthRequiredError: class extends Error {},
}));

describe("useAuthStore", () => {
  beforeEach(() => {
    useAuthStore.setState({ user: null, isLoading: true });
    vi.clearAllMocks();
  });

  it("initial state has no user and isLoading true", () => {
    const state = useAuthStore.getState();
    expect(state.user).toBeNull();
    expect(state.isLoading).toBe(true);
  });

  it("login sets user and token", async () => {
    const mockUser = { user_id: "u1", email: "a@b.com", username: "alice", email_verified: false, created_at: "" };
    vi.mocked(apiClient.post).mockResolvedValue({ access_token: "tok", user: mockUser });
    await useAuthStore.getState().login("a@b.com", "pass");
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(apiClient.setAccessToken).toHaveBeenCalledWith("tok");
  });

  it("register calls post with correct payload", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({});
    await useAuthStore.getState().register("a@b.com", "alice", "pass123");
    expect(apiClient.post).toHaveBeenCalledWith("/api/auth/register", { email: "a@b.com", username: "alice", password: "pass123" });
  });

  it("logout clears user and token", async () => {
    useAuthStore.setState({ user: { user_id: "u1", email: "a@b.com", username: "a", email_verified: false, created_at: "" } });
    vi.mocked(apiClient.post).mockResolvedValue({});
    await useAuthStore.getState().logout();
    expect(useAuthStore.getState().user).toBeNull();
    expect(apiClient.setAccessToken).toHaveBeenCalledWith(null);
  });

  it("loadCurrentUser sets user on success", async () => {
    const mockUser = { user_id: "u1", email: "a@b.com", username: "alice", email_verified: false, created_at: "" };
    vi.mocked(apiClient.get).mockResolvedValue(mockUser);
    await useAuthStore.getState().loadCurrentUser();
    expect(useAuthStore.getState().user).toEqual(mockUser);
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("loadCurrentUser sets null on AuthRequiredError", async () => {
    const { AuthRequiredError } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockRejectedValue(new AuthRequiredError());
    await useAuthStore.getState().loadCurrentUser();
    expect(useAuthStore.getState().user).toBeNull();
    expect(useAuthStore.getState().isLoading).toBe(false);
  });

  it("login calls post with correct payload", async () => {
    const mockUser = { user_id: "u1", email: "a@b.com", username: "a", email_verified: false, created_at: "" };
    vi.mocked(apiClient.post).mockResolvedValue({ access_token: "t", user: mockUser });
    await useAuthStore.getState().login("a@b.com", "pass");
    expect(apiClient.post).toHaveBeenCalledWith("/api/auth/login", { email_or_username: "a@b.com", password: "pass" });
  });

  it("logout calls post to /api/auth/logout", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({});
    await useAuthStore.getState().logout();
    expect(apiClient.post).toHaveBeenCalledWith("/api/auth/logout", {});
  });

  it("loadCurrentUser calls get /api/auth/me", async () => {
    vi.mocked(apiClient.get).mockResolvedValue({ user_id: "u1", email: "a@b.com", username: "a", email_verified: false, created_at: "" });
    await useAuthStore.getState().loadCurrentUser();
    expect(apiClient.get).toHaveBeenCalledWith("/api/auth/me");
  });

  it("login failure does not set user", async () => {
    vi.mocked(apiClient.post).mockRejectedValue(new Error("bad"));
    await expect(useAuthStore.getState().login("a@b.com", "bad")).rejects.toThrow();
    expect(useAuthStore.getState().user).toBeNull();
  });
});
