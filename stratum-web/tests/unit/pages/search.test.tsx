import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import SearchPage from "@/app/(app)/search/page";

vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn() },
  AuthRequiredError: class extends Error {},
}));

import { beforeEach } from "vitest";

function Wrapper({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("SearchPage", () => {
  beforeEach(() => { vi.clearAllMocks(); });
  it("renders search input and button", () => {
    render(<SearchPage />, { wrapper: Wrapper });
    expect(screen.getByPlaceholderText(/搜索/)).toBeDefined();
    expect(screen.getByRole("button", { name: /搜索/ })).toBeDefined();
  });

  it("renders heading", () => {
    render(<SearchPage />, { wrapper: Wrapper });
    expect(screen.getByRole("heading", { name: "搜索" })).toBeDefined();
  });

  it("button disabled while searching", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockImplementation(() => new Promise(() => {}));
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    await waitFor(() => {
      expect(screen.getByRole("button").textContent).toContain("搜索中");
    });
  });

  it("shows results after search", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({
      results: [{ id: "1", type: "substrate", title: "Test Doc", score: 0.95, highlight: null }],
      query_used: "test",
    });
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "test" } });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    await waitFor(() => {
      expect(screen.getByText("Test Doc")).toBeDefined();
      expect(screen.getByText("95%")).toBeDefined();
    });
  });

  it("shows result count", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({
      results: [{ id: "1", type: "substrate", title: "A", score: 0.9, highlight: null }],
      query_used: "q",
    });
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "q" } });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    await waitFor(() => {
      expect(screen.getByText(/找到 1 条结果/)).toBeDefined();
    });
  });

  it("shows no results message", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({ results: [], query_used: "nothing" });
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "nothing" } });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    await waitFor(() => {
      expect(screen.getByText("无结果")).toBeDefined();
    });
  });

  it("shows error on failure", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockRejectedValue(new Error("Network error"));
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "fail" } });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    await waitFor(() => {
      expect(screen.getByText(/搜索失败/)).toBeDefined();
    });
  });

  it("does not search on empty query", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({ results: [], query_used: "" });
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("result links to /documents/:id", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({
      results: [{ id: "doc123", type: "substrate", title: "Doc", score: 0.8, highlight: null }],
      query_used: "q",
    });
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "q" } });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    await waitFor(() => {
      const link = screen.getByText("Doc").closest("a");
      expect(link?.getAttribute("href")).toBe("/documents/doc123");
    });
  });

  it("shows type badge on results", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({
      results: [{ id: "1", type: "note", title: "N", score: 0.7, highlight: null }],
      query_used: "q",
    });
    render(<SearchPage />, { wrapper: Wrapper });
    fireEvent.change(screen.getByPlaceholderText(/搜索/), { target: { value: "q" } });
    fireEvent.click(screen.getByRole("button", { name: /搜索/ }));
    await waitFor(() => {
      expect(screen.getByText("note")).toBeDefined();
    });
  });
});
