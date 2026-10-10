/**
 * Wave 8/12 page unit tests — Block integration
 *
 * - JobsPage:      OScheduledJobsManager (Block renders job data)
 * - DocumentsPage: ODocumentTree (Block renders substrate list)
 * - NotePage:      ODocumentReader + OBacklinkPanel (mocked — note data needed)
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, within } from "@testing-library/react";
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

// Stub all @helios/blocks used in these pages
vi.mock("@helios/blocks", () => ({
  // OScheduledJobsManager: renders job name + toggle + delete per job
  OScheduledJobsManager: ({
    jobs,
    onToggleEnabled,
    onDelete,
  }: {
    jobs: Array<{ id: string; name: string; enabled: boolean; is_builtin?: boolean }>;
    onToggleEnabled?: (job: { id: string; enabled: boolean }, v: boolean) => void;
    onDelete?: (job: { id: string }) => void;
  }) => (
    <div data-testid="jobs-manager">
      {jobs.length === 0 && <p>暂无定时任务</p>}
      {jobs.map((job) => (
        <div key={job.id}>
          <span>{job.name}</span>
          <button onClick={() => onToggleEnabled?.(job, !job.enabled)}>
            {job.enabled ? "启用" : "禁用"}
          </button>
          {!job.is_builtin && (
            <button onClick={() => onDelete?.(job)}>删除</button>
          )}
        </div>
      ))}
    </div>
  ),
  // ODocumentTree: renders substrates as clickable items
  ODocumentTree: ({
    substrates,
    onSelect,
    emptyText,
  }: {
    substrates: Array<{ id: string; title: string | null }>;
    onSelect?: (s: { id: string }) => void;
    emptyText?: string;
  }) => (
    <div data-testid="document-tree">
      {substrates.length === 0 && <p>{emptyText ?? "暂无文档"}</p>}
      {substrates.map((s) => (
        <button key={s.id} onClick={() => onSelect?.(s)}>
          {s.title ?? s.id}
        </button>
      ))}
    </div>
  ),
  // ODocumentReader: render just the substrate title in a div (not h1 to avoid collision)
  ODocumentReader: ({ substrate }: { substrate: { title: string | null } }) => (
    <div data-testid="document-reader">
      <p>{substrate.title ?? "无标题"}</p>
    </div>
  ),
  // OBacklinkPanel: render backlinks list
  OBacklinkPanel: ({
    backlinks,
    onSelect,
    emptyText,
  }: {
    backlinks: Array<{ note: { id: string; title: string | null } }>;
    onSelect?: (item: { note: { id: string } }) => void;
    emptyText?: string;
  }) => (
    <div data-testid="backlink-panel">
      {backlinks.length === 0 && <p>{emptyText ?? "暂无反链"}</p>}
      {backlinks.map((b) => (
        <button key={b.note.id} onClick={() => onSelect?.(b)}>
          {b.note.title ?? b.note.id}
        </button>
      ))}
    </div>
  ),
  OAnnotationLayer: () => <div data-testid="annotation-layer" />,
  OCitationCard: () => <div data-testid="citation-card" />,
}));

vi.mock("@/components/shared/ShareNoteButton", () => ({
  ShareNoteButton: () => <button>分享</button>,
}));

function W({ children }: { children: React.ReactNode }) {
  return (
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      {children}
    </QueryClientProvider>
  );
}

// ---------------------------------------------------------------------------
// JobsPage
// ---------------------------------------------------------------------------
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
      items: [{ id: "j1", name: "Daily", agent_name: "daily_digest", cron_expression: "0 8 * * *", timezone: "UTC", enabled: true }],
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
      items: [{ id: "j1", name: "J", agent_name: "daily_digest", cron_expression: "* * * * *", timezone: "UTC", enabled: true }],
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
    // Use a non-builtin agent so is_builtin=false and delete button renders
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [{ id: "j1", name: "J", agent_name: "translation_worker", cron_expression: "* * * * *", timezone: "UTC", enabled: false }],
      total: 1,
    });
    render(<JobsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("删除")).toBeDefined());
  });
});

// ---------------------------------------------------------------------------
// DocumentsPage
// ---------------------------------------------------------------------------
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

// ---------------------------------------------------------------------------
// NotePage (uses ODocumentReader + OBacklinkPanel)
// ---------------------------------------------------------------------------
describe("NoteViewPage (backlinks)", () => {
  const NOTE_DETAIL = {
    id: "test-id",
    title: "My Note",
    content: "Some content",
    wikilinks: [],
    substrate_id: null,
    meta_json: {},
    created_at: "2026-01-01T00:00:00",
    updated_at: "2026-01-01T00:00:00",
  };

  beforeEach(() => { vi.clearAllMocks(); mockPush.mockClear(); });

  it("renders note title via ODocumentReader stub", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.endsWith("/backlinks")) return Promise.resolve({ items: [], total: 0 });
      return Promise.resolve(NOTE_DETAIL);
    });
    render(<NoteViewPage />, { wrapper: W });
    // The page also renders title as <h1>; scope to ODocumentReader container to be precise
    await waitFor(() => {
      const reader = screen.getByTestId("document-reader");
      expect(within(reader).getByText("My Note")).toBeDefined();
    });
  });

  it("shows backlinks via OBacklinkPanel stub", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.endsWith("/backlinks"))
        return Promise.resolve({
          items: [{ id: "n1", title: "Linked Note", snippet: "some text" }],
          total: 1,
        });
      return Promise.resolve(NOTE_DETAIL);
    });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("Linked Note")).toBeDefined());
  });

  it("shows empty state in OBacklinkPanel", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.endsWith("/backlinks")) return Promise.resolve({ items: [], total: 0 });
      return Promise.resolve(NOTE_DETAIL);
    });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("暂无反链")).toBeDefined());
  });

  it("clicking backlink navigates via OBacklinkPanel stub", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.endsWith("/backlinks"))
        return Promise.resolve({
          items: [{ id: "n2", title: "Other", snippet: null }],
          total: 1,
        });
      return Promise.resolve(NOTE_DETAIL);
    });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => screen.getByText("Other"));
    fireEvent.click(screen.getByText("Other"));
    expect(mockPush).toHaveBeenCalledWith("/notes/n2");
  });
});
