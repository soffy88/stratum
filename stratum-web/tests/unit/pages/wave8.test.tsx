import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import JobsPage from "@/app/(app)/jobs/page";
import DocumentsPage from "@/app/(app)/documents/page";
import NoteViewPage from "@/app/(app)/notes/[id]/page";

const mockPush = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mockPush }),
  useParams: () => ({ id: "test-id" }),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: { get: vi.fn(), post: vi.fn(), put: vi.fn(), delete: vi.fn() },
  AuthRequiredError: class extends Error {},
}));

function W({ children }: { children: React.ReactNode }) {
  return <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>{children}</QueryClientProvider>;
}

describe("JobsPage", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders heading", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("定时任务")).toBeDefined());
  });

  it("shows jobs list", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "j1", name: "Daily", agent_name: "digest", cron_expression: "0 8 * * *", timezone: "UTC", enabled: true }],
      total: 1,
    });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("Daily")).toBeDefined());
  });

  it("shows empty state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText(/暂无定时任务/)).toBeDefined());
  });

  it("toggle button shows enabled/disabled", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "j1", name: "J", agent_name: "a", cron_expression: "* * * * *", timezone: "UTC", enabled: true }],
      total: 1,
    });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("启用")).toBeDefined());
  });

  it("has create button", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("新建")).toBeDefined());
  });

  it("shows create form on click", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => screen.getByText("新建"));
    fireEvent.click(screen.getByText("新建"));
    expect(screen.getByPlaceholderText("任务名称")).toBeDefined();
  });

  it("has delete button per job", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "j1", name: "J", agent_name: "a", cron_expression: "* * * * *", timezone: "UTC", enabled: false }],
      total: 1,
    });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("删除")).toBeDefined());
  });
});

describe("DocumentsPage", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders heading", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<DocumentsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("文档")).toBeDefined());
  });

  it("shows substrate list", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "s1", title: "My PDF", mime: "application/pdf", language: "zh", page_count: 10 }],
      total: 1,
    });
    render(<DocumentsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("My PDF")).toBeDefined());
  });

  it("shows empty state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<DocumentsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText(/暂无文档/)).toBeDefined());
  });

  it("clicking doc navigates to /documents/:id", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "doc1", title: "Doc", mime: null, language: null, page_count: null }],
      total: 1,
    });
    render(<DocumentsPage />, { wrapper: W });
    await waitFor(() => screen.getByText("Doc"));
    fireEvent.click(screen.getByText("Doc"));
    expect(mockPush).toHaveBeenCalledWith("/documents/doc1");
  });
});

describe("NoteViewPage (backlinks)", () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it("renders heading", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("笔记反链")).toBeDefined());
  });

  it("shows backlinks", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "n1", title: "Linked Note", snippet: "some text" }],
      total: 1,
    });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("Linked Note")).toBeDefined());
  });

  it("shows empty state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText(/暂无反链/)).toBeDefined());
  });

  it("clicking backlink navigates", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "n2", title: "Other", snippet: null }],
      total: 1,
    });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => screen.getByText("Other"));
    fireEvent.click(screen.getByText("Other"));
    expect(mockPush).toHaveBeenCalledWith("/notes/n2");
  });
});
