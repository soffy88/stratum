/**
 * Unit tests for UrlIngestDialog — 当前实现(§2.4 Dialog 版)
 * 覆盖: 表单渲染 / 按钮态 / 取消 / 加载中 / 提交成功 / 提交失败
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UrlIngestDialog } from "@/components/UrlIngestDialog";

vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn() },
  AuthRequiredError: class extends Error {},
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));

function renderDialog(props?: Partial<Parameters<typeof UrlIngestDialog>[0]>) {
  const onClose = vi.fn();
  const onIngested = vi.fn();
  render(<UrlIngestDialog open={true} onClose={onClose} onIngested={onIngested} {...props} />);
  return { onClose, onIngested };
}

describe("UrlIngestDialog", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders all form fields", () => {
    renderDialog();
    expect(screen.getByPlaceholderText(/https:\/\/\.\.\./i)).toBeInTheDocument();
    expect(screen.getByText("AI 处理选项")).toBeInTheDocument();
    expect(screen.getByText("提取 Markdown")).toBeInTheDocument();
    expect(screen.getByText("翻译为中文")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /抓取/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /取消/i })).toBeInTheDocument();
  });

  it("fetch button disabled when URL empty", () => {
    renderDialog();
    expect(screen.getByRole("button", { name: /抓取/i })).toBeDisabled();
  });

  it("fetch button enabled when URL filled", () => {
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/\.\.\./i), {
      target: { value: "https://example.com" },
    });
    expect(screen.getByRole("button", { name: /抓取/i })).not.toBeDisabled();
  });

  it("close button (取消) calls onClose", () => {
    const { onClose } = renderDialog();
    fireEvent.click(screen.getByRole("button", { name: /取消/i }));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows loading state while fetching and disables button", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockImplementation(() => new Promise(() => {})); // never resolves
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/\.\.\./i), {
      target: { value: "https://example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText("抓取中…")).toBeInTheDocument());
    expect(screen.getByRole("button", { name: /抓取中…/ })).toBeDisabled();
  });

  it("submits url and selected derivatives on fetch", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({ ok: true });
    const { onIngested, onClose } = renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/\.\.\./i), {
      target: { value: "https://example.com/article" },
    });
    // 勾选"翻译为中文" → derivatives 含 translation
    fireEvent.click(screen.getByText("翻译为中文"));
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalled());
    const [calledUrl, body] = vi.mocked(apiClient.post).mock.calls[0]!;
    expect(calledUrl).toBe("/api/v1/inbox/submit");
    expect(body).toMatchObject({
      url: "https://example.com/article",
      generate_derivatives: ["translation"],
    });
    await waitFor(() => expect(onIngested).toHaveBeenCalledOnce());
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("shows error toast and re-enables button on failure", async () => {
    const { toast } = await import("sonner");
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockRejectedValue(new Error("boom"));
    const { onIngested, onClose } = renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/\.\.\./i), {
      target: { value: "https://example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));

    await waitFor(() => expect(toast.error).toHaveBeenCalledWith("抓取失败"));
    expect(onIngested).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /抓取/i })).not.toBeDisabled();
  });
});
