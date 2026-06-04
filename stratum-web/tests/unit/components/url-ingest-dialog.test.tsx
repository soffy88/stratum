/**
 * Unit tests for UrlIngestDialog — Phase 17.5 D1-D4
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { UrlIngestDialog } from "@/components/UrlIngestDialog";

// Mock apiClient
vi.mock("@/lib/api-client", () => ({
  apiClient: { getAccessToken: () => "test-token" },
}));

function renderDialog(props?: Partial<Parameters<typeof UrlIngestDialog>[0]>) {
  const onClose = vi.fn();
  const onSuccess = vi.fn();
  render(<UrlIngestDialog onClose={onClose} onSuccess={onSuccess} {...props} />);
  return { onClose, onSuccess };
}

describe("UrlIngestDialog — Phase 17.5", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  // D1: Fields render
  it("renders all D1 form fields", () => {
    renderDialog();
    expect(screen.getByPlaceholderText(/https:\/\/example.com/i)).toBeInTheDocument();
    expect(screen.getByText(/留空自动/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/凯利公式, quant/i)).toBeInTheDocument();
    expect(screen.getByText("全文")).toBeInTheDocument();
    expect(screen.getByText(/摘要/i)).toBeInTheDocument();
    expect(screen.getByPlaceholderText(/这篇讲了/i)).toBeInTheDocument();
  });

  it("fetch button disabled when URL empty", () => {
    renderDialog();
    const btn = screen.getByRole("button", { name: /抓取/i });
    expect(btn).toBeDisabled();
  });

  it("fetch button enabled when URL filled", () => {
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://example.com" },
    });
    const btn = screen.getByRole("button", { name: /抓取/i });
    expect(btn).not.toBeDisabled();
  });

  it("close button calls onClose", () => {
    const { onClose } = renderDialog();
    fireEvent.click(screen.getByText("×"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  // D2: Loading state
  it("shows loading spinner while fetching", async () => {
    vi.spyOn(global, "fetch").mockImplementation(
      () => new Promise(() => {}), // never resolves
    );
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText(/正在抓取/i)).toBeInTheDocument());
  });

  it("loading shows hostname from URL", async () => {
    vi.spyOn(global, "fetch").mockImplementation(() => new Promise(() => {}));
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://news.example.com/article" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() =>
      expect(screen.getByText(/news\.example\.com/)).toBeInTheDocument(),
    );
  });

  // D3: Success state
  it("shows success preview after successful fetch", async () => {
    const mockResult = {
      substrate_id: "01TEST123",
      status: "completed",
      url: "https://example.com",
      title: "Test Article Title",
      snippet: "This is the article snippet...",
      word_count: 1234,
      medium: "webpage",
      tags: ["tag1", "tag2"],
    };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResult), { status: 200 }),
    );
    const { onSuccess } = renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));

    await waitFor(() => expect(screen.getByText("✓ 抓取成功，已入库")).toBeInTheDocument());
    expect(screen.getByText("Test Article Title")).toBeInTheDocument();
    expect(screen.getByText(/1,234/)).toBeInTheDocument();
    expect(onSuccess).toHaveBeenCalledWith("01TEST123");
  });

  it("shows 查看完整 link with correct substrate id", async () => {
    const mockResult = {
      substrate_id: "01TESTID",
      status: "completed",
      url: "https://example.com",
      title: "Title",
      snippet: "Snippet",
      word_count: 500,
      medium: "webpage",
      tags: [],
    };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResult), { status: 200 }),
    );
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText(/查看完整/)).toBeInTheDocument());
    expect(screen.getByText(/查看完整/).closest("a")).toHaveAttribute(
      "href",
      "/documents/01TESTID",
    );
  });

  it("继续抓另一个 resets form", async () => {
    const mockResult = {
      substrate_id: "01TEST",
      status: "completed",
      url: "https://example.com",
      title: "T",
      snippet: "S",
      word_count: 100,
      medium: "webpage",
      tags: [],
    };
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify(mockResult), { status: 200 }),
    );
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://example.com" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText("继续抓另一个")).toBeInTheDocument());
    fireEvent.click(screen.getByText("继续抓另一个"));
    expect(screen.getByPlaceholderText(/https:\/\/example.com/i)).toBeInTheDocument();
  });

  // D4: Error handling
  it("shows friendly error for 404", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "not_found" }), { status: 404 }),
    );
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://example.com/missing" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText(/404 不存在/)).toBeInTheDocument());
  });

  it("shows ssrf_blocked error with correct message", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "ssrf_blocked" }), { status: 403 }),
    );
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "http://192.168.1.1/" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText(/内网地址/)).toBeInTheDocument());
  });

  it("shows timeout error with browser extension hint", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "fetch_timeout" }), { status: 504 }),
    );
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "https://slow.example.com/" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText(/超时/)).toBeInTheDocument());
    expect(screen.getByText(/浏览器扩展/)).toBeInTheDocument();
  });

  it("retry button resets to input phase", async () => {
    vi.spyOn(global, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "ssrf_blocked" }), { status: 403 }),
    );
    renderDialog();
    fireEvent.change(screen.getByPlaceholderText(/https:\/\/example.com/i), {
      target: { value: "http://192.168.1.1/" },
    });
    fireEvent.click(screen.getByRole("button", { name: /抓取/i }));
    await waitFor(() => expect(screen.getByText("重试")).toBeInTheDocument());
    fireEvent.click(screen.getByText("重试"));
    expect(screen.getByPlaceholderText(/https:\/\/example.com/i)).toBeInTheDocument();
  });
});
