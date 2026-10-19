/**
 * Wave 8/12 page unit tests — Block integration
 *
 * - JobsPage:      OScheduledJobsManager (Block renders job data)
 * - DocumentsPage: ODocumentTree (Block renders substrate list)
 * - NotePage:      WikilinkNoteBody(OMarkdownRenderer) + OBacklinkPanel +
 *                  OutgoingLinksPanel + NoteHistoryPanel(OEventTimeline) (mocked)
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
  // OMarkdownRenderer: render raw markdown content (wikilinks pre-rewritten to links)
  OMarkdownRenderer: ({ content }: { content: string }) => (
    <div data-testid="markdown-renderer">{content}</div>
  ),
  // OEventTimeline: render events with always-visible detail (for restore flow tests)
  OEventTimeline: ({
    events,
    emptyMessage,
    onEventClick,
  }: {
    events: Array<{ id: string; title: string; detail?: React.ReactNode }>;
    emptyMessage?: string;
    onEventClick?: (e: { id: string }) => void;
  }) => (
    <div data-testid="event-timeline">
      {events.length === 0 ? (
        <p>{emptyMessage ?? "暂无事件"}</p>
      ) : (
        events.map((e) => (
          <div key={e.id}>
            <button onClick={() => onEventClick?.(e)}>{e.title}</button>
            {e.detail}
          </div>
        ))
      )}
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
    // apiClient.ts 包装层会自动包一层 data; mock 需返回原始形状。
    // BackgroundTasksPanel 走同一条包装链, folder-watch/channels/sources 需返回数组。
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith("/api/v1/documents") && !url.includes("kind=")) {
        return Promise.resolve({
          items: [{ id: "s1", title: "My PDF", mime: "application/pdf", language: "zh", page_count: 10, medium: "pdf", source: "upload", created_at: "2026-01-01T00:00:00", is_pinned: false }],
          total: 1,
        });
      }
      if (url.startsWith("/api/v1/documents")) return Promise.resolve({ items: [], total: 0 });
      return Promise.resolve([]);
    });
    render(<DocumentsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("My PDF")).toBeDefined());
  });

  it("shows empty state", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith("/api/v1/documents")) return Promise.resolve({ items: [], total: 0 });
      return Promise.resolve([]);
    });
    render(<DocumentsPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText(/暂无文档/)).toBeDefined());
  });

  it("clicking doc navigates to /documents/:id", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.startsWith("/api/v1/documents") && !url.includes("kind=")) {
        return Promise.resolve({
          items: [{ id: "doc1", title: "Doc", mime: null, language: null, page_count: null, medium: "text", source: "upload", created_at: "2026-01-01T00:00:00", is_pinned: false }],
          total: 1,
        });
      }
      if (url.startsWith("/api/v1/documents")) return Promise.resolve({ items: [], total: 0 });
      return Promise.resolve([]);
    });
    render(<DocumentsPage />, { wrapper: W });
    await waitFor(() => screen.getByText("Doc"));
    fireEvent.click(screen.getByText("Doc"));
    expect(mockPush).toHaveBeenCalledWith("/documents/doc1");
  });
});

// ---------------------------------------------------------------------------
// ---------------------------------------------------------------------------
// NotePage (WikilinkNoteBody + OBacklinkPanel + 出链 + 版本历史)
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

  const NOTE_LIST = [{ id: "n1", title: "目标笔记", updated_at: "2026-01-02T00:00:00" }];

  const REVISIONS = [
    { version: 2, title: "My Note", cause: "编辑", author: "tester", created_at: "2026-01-03T00:00:00" },
    { version: 1, title: "My Note", cause: "创建", author: "tester", created_at: "2026-01-01T00:00:00" },
  ];

  const EMPTY_LINKS = { items: [], total: 0 };

  beforeEach(() => { vi.clearAllMocks(); mockPush.mockClear(); });

  async function mockNotePage(backlinks: unknown, note: unknown, list: unknown, revisions: unknown) {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockImplementation((url: string) => {
      if (url.endsWith("/backlinks")) return Promise.resolve(backlinks);
      if (url === "/api/v1/notes") return Promise.resolve(list);
      if (url.endsWith("/revisions")) return Promise.resolve(revisions);
      return Promise.resolve(note);
    });
  }

  it("renders note title and markdown body", async () => {
    await mockNotePage(EMPTY_LINKS, NOTE_DETAIL, [], []);
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByRole("heading", { name: "My Note" })).toBeDefined());
    const body = screen.getByTestId("markdown-renderer");
    expect(within(body).getByText("Some content")).toBeDefined();
  });

  it("renders [[id]] as a markdown note link", async () => {
    await mockNotePage(EMPTY_LINKS, { ...NOTE_DETAIL, content: "见 [[n1]]" }, NOTE_LIST, []);
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() =>
      expect(screen.getByTestId("markdown-renderer").textContent).toContain("[目标笔记](/notes/n1)"),
    );
  });

  it("shows backlinks via OBacklinkPanel stub", async () => {
    await mockNotePage(
      { items: [{ id: "n1", title: "Linked Note", snippet: "some text" }], total: 1 },
      NOTE_DETAIL,
      [],
      [],
    );
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("Linked Note")).toBeDefined());
  });

  it("shows empty state in OBacklinkPanel", async () => {
    await mockNotePage(EMPTY_LINKS, NOTE_DETAIL, [], []);
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("暂无反链")).toBeDefined());
  });

  it("clicking backlink navigates via OBacklinkPanel stub", async () => {
    await mockNotePage(
      { items: [{ id: "n2", title: "Other", snippet: null }], total: 1 },
      NOTE_DETAIL,
      [],
      [],
    );
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => screen.getByText("Other"));
    fireEvent.click(screen.getByText("Other"));
    expect(mockPush).toHaveBeenCalledWith("/notes/n2");
  });

  it("outgoing panel lists resolved links and navigates", async () => {
    await mockNotePage(EMPTY_LINKS, { ...NOTE_DETAIL, content: "见 [[n1]]" }, NOTE_LIST, []);
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("这篇笔记链向谁")).toBeDefined());
    fireEvent.click(screen.getByText("目标笔记"));
    expect(mockPush).toHaveBeenCalledWith("/notes/n1");
  });

  it("history panel lists versions and restore posts to the API", async () => {
    const { apiClient } = await import("@/lib/api-client");
    await mockNotePage(EMPTY_LINKS, NOTE_DETAIL, [], REVISIONS);
    vi.mocked(apiClient.post).mockResolvedValue({ status: "restored" });
    render(<NoteViewPage />, { wrapper: W });
    await waitFor(() => expect(screen.getByText("第 2 版")).toBeDefined());
    expect(screen.getByText("第 1 版")).toBeDefined();
    const restoreButtons = screen.getAllByText("恢复到这一版");
    fireEvent.click(restoreButtons[restoreButtons.length - 1]!);
    fireEvent.click(screen.getByText("确认恢复"));
    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/api/v1/notes/test-id/revisions/1/restore", {}),
    );
  });
});
