/**
 * AIPage unit tests — Wave 12 (Block integration)
 *
 * Strategy: mock OAIQAPanel and OAISummaryCard to expose testable
 * interfaces. Tests verify adapter callbacks and data flow.
 */
import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider, QueryClient } from "@tanstack/react-query";
import AIPage from "@/app/(app)/ai/page";

// Stub Blocks to expose testable interfaces
vi.mock("@helios/blocks", () => ({
  OAIQAPanel: ({
    onAsk,
    placeholder,
  }: {
    onAsk: (q: string) => Promise<{ answer: string; citations: unknown[] }>;
    placeholder?: string;
  }) => {
    const [val, setVal] = vi.fn ? ["",(s: string) => s] : ["", () => {}];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const [input, setInput] = (globalThis as any).__aiInput__ ?? ["", () => {}];
    return (
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const fd = new FormData(e.currentTarget as HTMLFormElement);
          const q = fd.get("question") as string;
          if (!q?.trim()) return;
          try {
            const res = await onAsk(q);
            const el = document.getElementById("qa-answer");
            if (el) el.textContent = res.answer;
          } catch (err) {
            const el = document.getElementById("qa-error");
            if (el) el.textContent = `错误: ${(err as Error).message}`;
          }
        }}
      >
        <input name="question" placeholder={placeholder ?? "问一个关于你的文档的问题..."} />
        <button type="submit">提问</button>
        <div id="qa-answer" />
        <div id="qa-error" />
      </form>
    );
  },
  OAISummaryCard: ({
    summary,
    digestSent,
  }: {
    summary: string;
    date?: string;
    digestSent?: boolean;
    citations?: unknown[];
  }) => (
    <div>
      <p>{summary}</p>
      {digestSent && <span>completed</span>}
    </div>
  ),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: { post: vi.fn(), get: vi.fn() },
  AuthRequiredError: class extends Error {},
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

describe("AIPage", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
  });

  it("renders heading and tabs", () => {
    render(<AIPage />, { wrapper: W });
    expect(screen.getByRole("heading", { name: "AI 助手" })).toBeDefined();
    expect(screen.getByText("问答")).toBeDefined();
    expect(screen.getByText("摘要")).toBeDefined();
  });

  it("QA tab is default — OAIQAPanel placeholder visible", () => {
    render(<AIPage />, { wrapper: W });
    expect(screen.getByPlaceholderText(/问一个/)).toBeDefined();
  });

  it("QA submit calls POST /api/agents/reading_companion/run", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({
      agent_run: { id: "r1", agent_name: "reading_companion", status: "pending", output: null },
      message: "Agent execution pending",
    });
    const user = userEvent.setup();
    render(<AIPage />, { wrapper: W });
    await user.type(screen.getByPlaceholderText(/问一个/), "What is X?");
    await user.click(screen.getByRole("button", { name: "提问" }));
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        "/api/agents/reading_companion/run",
        { params: { query: "What is X?" } }
      );
    });
  });

  it("QA shows agent response message after answer", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockResolvedValue({
      agent_run: { id: "r1", agent_name: "reading_companion", status: "pending", output: null },
      message: "Agent execution is not available",
    });
    const user = userEvent.setup();
    render(<AIPage />, { wrapper: W });
    await user.type(screen.getByPlaceholderText(/问一个/), "Q");
    await user.click(screen.getByRole("button", { name: "提问" }));
    await waitFor(() => {
      // adapter maps message → QAResponse.answer
      expect(screen.getByText("Agent execution is not available")).toBeDefined();
    });
  });

  it("QA shows error on failure", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.post).mockRejectedValue(new Error("Agent failed"));
    const user = userEvent.setup();
    render(<AIPage />, { wrapper: W });
    await user.type(screen.getByPlaceholderText(/问一个/), "Q");
    await user.click(screen.getByRole("button", { name: "提问" }));
    await waitFor(() => {
      expect(screen.getByText(/错误: Agent failed/)).toBeDefined();
    });
  });

  it("QA does not call API on empty question", async () => {
    const { apiClient } = await import("@/lib/api-client");
    const user = userEvent.setup();
    render(<AIPage />, { wrapper: W });
    await user.click(screen.getByRole("button", { name: "提问" }));
    expect(vi.mocked(apiClient.post)).not.toHaveBeenCalled();
  });

  it("switching to Summary tab shows content", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [
        {
          id: "r1",
          agent_name: "daily_digest",
          status: "completed",
          output: "Today summary",
          started_at: "2026-01-01T00:00:00",
        },
      ],
      total: 1,
    });
    const user = userEvent.setup();
    render(<AIPage />, { wrapper: W });
    await user.click(screen.getByText("摘要"));
    await waitFor(() => {
      expect(screen.getByText("Today summary")).toBeDefined();
    });
  });

  it("Summary tab shows empty state when no runs", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({ items: [], total: 0 });
    const user = userEvent.setup();
    render(<AIPage />, { wrapper: W });
    await user.click(screen.getByText("摘要"));
    await waitFor(() => {
      expect(screen.getByText(/暂无摘要/)).toBeDefined();
    });
  });

  it("Summary shows digestSent badge for completed runs", async () => {
    const { apiClient } = await import("@/lib/api-client");
    vi.mocked(apiClient.get).mockResolvedValue({
      items: [
        { id: "r1", agent_name: "daily_digest", status: "completed", output: "X", started_at: null },
      ],
      total: 1,
    });
    const user = userEvent.setup();
    render(<AIPage />, { wrapper: W });
    await user.click(screen.getByText("摘要"));
    await waitFor(() => {
      expect(screen.getByText("completed")).toBeDefined();
    });
  });
});
