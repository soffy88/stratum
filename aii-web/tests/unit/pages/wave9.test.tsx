import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import SettingsPage from "@/app/(app)/settings/page";
import { ShareNoteButton } from "@/components/shared/ShareNoteButton";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
vi.mock("@/stores/auth", () => ({
  useAuthStore: () => ({ user: { username: "testuser", email: "test@t.com" } }),
}));
vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn(), get: vi.fn(), delete: vi.fn() },
  AuthRequiredError: class extends Error {},
}));

function W({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("SettingsPage", () => {
  it("renders heading", () => {
    render(<SettingsPage />, { wrapper: W });
    expect(screen.getByRole("heading", { name: "设置" })).toBeDefined();
  });

  it("shows profile tab by default", () => {
    render(<SettingsPage />, { wrapper: W });
    expect(screen.getByText("testuser")).toBeDefined();
    expect(screen.getByText("test@t.com")).toBeDefined();
  });

  it("switches to theme tab", () => {
    render(<SettingsPage />, { wrapper: W });
    fireEvent.click(screen.getByText("主题"));
    expect(screen.getByText("Zen (默认)")).toBeDefined();
  });

  it("theme tab shows 3 options", () => {
    render(<SettingsPage />, { wrapper: W });
    fireEvent.click(screen.getByText("主题"));
    expect(screen.getByText("Zen (默认)")).toBeDefined();
    expect(screen.getByText("Light")).toBeDefined();
    expect(screen.getByText("Dark")).toBeDefined();
  });

  it("profile tab shows username and email", () => {
    render(<SettingsPage />, { wrapper: W });
    expect(screen.getByText("testuser")).toBeDefined();
  });

  it("sessions tab button is present", () => {
    render(<SettingsPage />, { wrapper: W });
    expect(screen.getByText("会话管理")).toBeDefined();
  });

  it("switches to sessions tab and shows loading state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation(() => new Promise(() => {}));
    render(<SettingsPage />, { wrapper: W });
    fireEvent.click(screen.getByText("会话管理"));
    await waitFor(() => {
      expect(screen.getByText("加载中...")).toBeDefined();
    });
  });
});

describe("ShareNoteButton", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders share button", () => {
    render(<ShareNoteButton noteId="n1" />, { wrapper: W });
    expect(screen.getByText("分享")).toBeDefined();
  });

  it("calls API on click", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({ token: "abc", share_url: "/share/abc" });
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    render(<ShareNoteButton noteId="n1" />, { wrapper: W });
    fireEvent.click(screen.getByText("分享"));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/api/share/note/n1", { allow_anonymous: true });
    });
  });

  it("shows copied state after success", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({ token: "abc", share_url: "/share/abc" });
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockResolvedValue(undefined) } });
    render(<ShareNoteButton noteId="n1" />, { wrapper: W });
    fireEvent.click(screen.getByText("分享"));
    await waitFor(() => {
      expect(screen.getByText(/已复制/)).toBeDefined();
    });
  });

  it("shows loading state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockImplementation(() => new Promise(() => {}));
    render(<ShareNoteButton noteId="n1" />, { wrapper: W });
    fireEvent.click(screen.getByText("分享"));
    await waitFor(() => {
      expect(screen.getByText("生成中...")).toBeDefined();
    });
  });
});
