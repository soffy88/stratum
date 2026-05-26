import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import AIPage from "@/app/(app)/ai/page";

vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn(), get: vi.fn() },
  AuthRequiredError: class extends Error {},
}));

import { beforeEach } from "vitest";

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("AIPage", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
  });

  it("renders heading and tabs", () => {
    render(<AIPage />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: "AI 助手" })).toBeDefined();
    expect(screen.getByText("问答")).toBeDefined();
    expect(screen.getByText("摘要")).toBeDefined();
  });

  it("QA tab is default", () => {
    render(<AIPage />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/问一个/)).toBeDefined();
  });

  it("QA submit calls agent API", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(apiClient.post).mockResolvedValue({
      agent_run: { id: "r1", agent_name: "reading_companion", status: "pending", output: null },
      message: "Agent execution pending",
    });
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/问一个/), { target: { value: "What is X?" } });
    fireEvent.click(screen.getByRole("button", { name: /提问/ }));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/api/agents/reading_companion/run", { params: { query: "What is X?" } });
    });
  });

  it("QA shows agent response message", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(apiClient.post).mockResolvedValue({
      agent_run: { id: "r1", agent_name: "reading_companion", status: "pending", output: null },
      message: "Agent execution is not available",
    });
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/问一个/), { target: { value: "Q" } });
    fireEvent.click(screen.getByRole("button", { name: /提问/ }));
    await waitFor(() => {
      expect(screen.getByText(/not available/)).toBeDefined();
    });
  });

  it("QA shows error on failure", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    vi.mocked(apiClient.post).mockRejectedValue(new Error("Agent failed"));
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/问一个/), { target: { value: "Q" } });
    fireEvent.click(screen.getByRole("button", { name: /提问/ }));
    await waitFor(() => {
      expect(screen.getByText(/错误/)).toBeDefined();
    });
  });

  it("switching to Summary tab shows loading then content", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "r1", agent_name: "daily_digest", status: "completed", output: "Today summary", started_at: "2026-01-01T00:00:00" }],
      total: 1,
    });
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByText("摘要"));
    await waitFor(() => {
      expect(screen.getByText("Today summary")).toBeDefined();
    });
  });

  it("Summary tab shows empty state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByText("摘要"));
    await waitFor(() => {
      expect(screen.getByText(/暂无摘要/)).toBeDefined();
    });
  });

  it("QA does not submit empty question", async () => {
    const { apiClient } = await import("@/lib/api-client");
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button", { name: /提问/ }));
    // post should only have been called by beforeEach mock setup, not by submit
    const postCalls = vi.mocked(apiClient.post).mock.calls.filter(c => c[0]?.includes("agents"));
    expect(postCalls.length).toBe(0);
  });

  it("QA button shows loading state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockImplementation(() => new Promise(() => {}));
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/问一个/), { target: { value: "Q" } });
    fireEvent.click(screen.getByText("提问"));
    await waitFor(() => {
      expect(screen.getByText("思考中...")).toBeDefined();
    });
  });

  it("Summary shows status badge", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "r1", agent_name: "daily_digest", status: "completed", output: "X", started_at: null }],
      total: 1,
    });
    render(<AIPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByText("摘要"));
    await waitFor(() => {
      expect(screen.getByText("completed")).toBeDefined();
    });
  });
});
