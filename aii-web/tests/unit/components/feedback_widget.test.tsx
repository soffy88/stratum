import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import { FeedbackWidget } from "@/components/shared/FeedbackWidget";

vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn() },
  AuthRequiredError: class extends Error {},
}));

function W({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })}>
      {children}
    </QueryClientProvider>
  );
}

describe("FeedbackWidget", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders floating button initially", () => {
    render(<FeedbackWidget />, { wrapper: W });
    expect(screen.getByRole("button", { name: "发送反馈" })).toBeDefined();
  });

  it("opens form on floating button click", () => {
    render(<FeedbackWidget />, { wrapper: W });
    fireEvent.click(screen.getByRole("button", { name: "发送反馈" }));
    expect(screen.getByRole("heading", { name: "发送反馈" })).toBeDefined();
    expect(screen.getByPlaceholderText("告诉我们你的想法...")).toBeDefined();
  });

  it("closes form on × button click", () => {
    render(<FeedbackWidget />, { wrapper: W });
    fireEvent.click(screen.getByRole("button", { name: "发送反馈" }));
    fireEvent.click(screen.getByRole("button", { name: "关闭" }));
    expect(screen.getByRole("button", { name: "发送反馈" })).toBeDefined();
  });

  it("submit button disabled when content empty", () => {
    render(<FeedbackWidget />, { wrapper: W });
    fireEvent.click(screen.getByRole("button", { name: "发送反馈" }));
    const submitBtn = screen.getByRole("button", { name: "发送" });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it("submit button enabled when content typed", () => {
    render(<FeedbackWidget />, { wrapper: W });
    fireEvent.click(screen.getByRole("button", { name: "发送反馈" }));
    fireEvent.change(screen.getByPlaceholderText("告诉我们你的想法..."), {
      target: { value: "Great app!" },
    });
    const submitBtn = screen.getByRole("button", { name: "发送" });
    expect((submitBtn as HTMLButtonElement).disabled).toBe(false);
  });

  it("calls POST /api/feedback on submit", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({ status: "received" });
    render(<FeedbackWidget />, { wrapper: W });
    fireEvent.click(screen.getByRole("button", { name: "发送反馈" }));
    fireEvent.change(screen.getByPlaceholderText("告诉我们你的想法..."), {
      target: { value: "Nice feature" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith("/api/feedback", expect.objectContaining({ content: "Nice feature" }));
    });
  });

  it("shows success state after submit", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({ status: "received" });
    render(<FeedbackWidget />, { wrapper: W });
    fireEvent.click(screen.getByRole("button", { name: "发送反馈" }));
    fireEvent.change(screen.getByPlaceholderText("告诉我们你的想法..."), {
      target: { value: "Nice feature" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => {
      expect(screen.getByText("感谢你的反馈！")).toBeDefined();
    });
  });

  it("shows error message on API failure", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockRejectedValue(new Error("Network error"));
    render(<FeedbackWidget />, { wrapper: W });
    fireEvent.click(screen.getByRole("button", { name: "发送反馈" }));
    fireEvent.change(screen.getByPlaceholderText("告诉我们你的想法..."), {
      target: { value: "Error test" },
    });
    fireEvent.click(screen.getByRole("button", { name: "发送" }));
    await waitFor(() => {
      expect(screen.getByText("发送失败，请稍后重试")).toBeDefined();
    });
  });
});
