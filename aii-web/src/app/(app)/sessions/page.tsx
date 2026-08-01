"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import {
  listSessions,
  getSession,
  createSession,
  deleteSession,
  addMessage,
  getSessionContext,
  commitSession,
  getSessionMemories,
  type Session,
  type SessionDetail,
  type SessionContext as SessionContextType,
  type SessionMemories,
  type SessionMessage,
} from "@/lib/adapters/sessions";

const AUTO_COMMIT_THRESHOLD = 8000;

// ── Helpers ─────────────────────────────────────────────────

function relativeTime(dateStr: string): string {
  const diff = Date.now() - new Date(dateStr).getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs} 小时前`;
  const days = Math.floor(hrs / 24);
  if (days < 30) return `${days} 天前`;
  return dateStr.slice(0, 10);
}

function StatusBadge({ status }: { status: string }) {
  const cls =
    status === "active"
      ? "bg-green-500/20 text-green-400"
      : status === "committed"
        ? "bg-blue-500/20 text-blue-400"
        : "bg-gray-500/20 text-gray-400";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {status}
    </span>
  );
}

function RoleBadge({ role }: { role: string }) {
  const cls =
    role === "user"
      ? "bg-blue-500/20 text-blue-400"
      : role === "assistant"
        ? "bg-purple-500/20 text-purple-400"
        : "bg-gray-500/20 text-gray-400";
  return (
    <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${cls}`}>
      {role}
    </span>
  );
}

function MemoryTypeBadge({ type }: { type: string }) {
  return (
    <span className="text-xs px-2 py-0.5 rounded-full bg-yellow-500/20 text-yellow-400 font-medium">
      {type}
    </span>
  );
}

// ── Collapsible section ─────────────────────────────────────

function Collapsible({
  title,
  defaultOpen = true,
  children,
}: {
  title: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-[var(--color-foreground)] hover:bg-white/5 transition"
      >
        {title}
        <span className="text-[var(--color-muted)]">{open ? "▾" : "▸"}</span>
      </button>
      {open && <div className="px-4 pb-4">{children}</div>}
    </div>
  );
}

// ── Main page ───────────────────────────────────────────────

export default function SessionsPage() {
  const [sessions, setSessions] = useState<Session[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<SessionDetail | null>(null);
  const [ctx, setCtx] = useState<SessionContextType | null>(null);
  const [memories, setMemories] = useState<SessionMemories | null>(null);
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState<"messages" | "context" | "memories">("messages");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [messageInput, setMessageInput] = useState("");
  const [sending, setSending] = useState(false);
  const [contextQuery, setContextQuery] = useState("");
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Load sessions
  const loadSessions = useCallback(async () => {
    setLoading(true);
    const data = await listSessions();
    setSessions(data ?? []);
    setLoading(false);
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  // Load detail when selected
  useEffect(() => {
    if (!selectedId) {
      setDetail(null);
      setCtx(null);
      setMemories(null);
      return;
    }
    setDetailLoading(true);
    Promise.all([
      getSession(selectedId),
      getSessionContext(selectedId),
      getSessionMemories(selectedId),
    ]).then(([d, c, m]) => {
      setDetail(d);
      setCtx(c);
      setMemories(m);
      setDetailLoading(false);
    });
  }, [selectedId]);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [detail?.messages]);

  // Filter sessions
  const filtered = sessions
    .filter((s) =>
      s.title.toLowerCase().includes(search.toLowerCase())
    )
    .sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());

  // Handlers
  async function handleCreate() {
    const s = await createSession();
    if (s) {
      await loadSessions();
      setSelectedId(s.id);
    }
  }

  async function handleDelete(id: string) {
    if (!confirm("确定删除此会话？")) return;
    const ok = await deleteSession(id);
    if (ok) {
      if (selectedId === id) setSelectedId(null);
      await loadSessions();
    }
  }

  async function handleSend() {
    if (!selectedId || !messageInput.trim() || sending) return;
    setSending(true);
    const msg = await addMessage(selectedId, "user", messageInput.trim());
    if (msg) {
      setMessageInput("");
      // Reload detail
      const d = await getSession(selectedId);
      setDetail(d);
      await loadSessions();
    }
    setSending(false);
  }

  async function handleCommit() {
    if (!selectedId) return;
    const ok = await commitSession(selectedId);
    if (ok) {
      const d = await getSession(selectedId);
      setDetail(d);
      await loadSessions();
    }
  }

  async function handleContextSearch() {
    if (!selectedId) return;
    const c = await getSessionContext(selectedId, contextQuery || undefined);
    setCtx(c);
  }

  const session = detail?.session;
  const tokenProgress = session
    ? Math.min((session.pending_tokens / AUTO_COMMIT_THRESHOLD) * 100, 100)
    : 0;

  return (
    <div className="flex h-[calc(100vh-4rem)]">
      {/* ── Left pane: Session list ── */}
      <div className="w-[35%] min-w-[280px] border-r border-[var(--color-border)] flex flex-col">
        <div className="p-4 space-y-3">
          <div className="flex items-center justify-between">
            <h1 className="text-lg font-semibold text-[var(--color-foreground)]">会话管理</h1>
            <button
              onClick={handleCreate}
              className="rounded-lg bg-[var(--color-primary)] text-white px-3 py-1.5 text-sm hover:opacity-90 transition"
            >
              新建会话
            </button>
          </div>
          <input
            type="text"
            placeholder="搜索会话..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm bg-[var(--color-card)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
          />
        </div>

        <div className="flex-1 overflow-y-auto">
          {loading ? (
            <p className="p-4 text-sm text-[var(--color-muted)]">加载中...</p>
          ) : filtered.length === 0 ? (
            <p className="p-4 text-sm text-[var(--color-muted)]">暂无会话</p>
          ) : (
            <div className="space-y-1 px-2 pb-4">
              {filtered.map((s) => (
                <button
                  key={s.id}
                  onClick={() => setSelectedId(s.id)}
                  className={`w-full text-left p-3 rounded-xl transition ${
                    selectedId === s.id
                      ? "bg-[var(--color-primary)]/10 border border-[var(--color-primary)]/30"
                      : "border border-transparent hover:bg-white/5"
                  }`}
                >
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-[var(--color-foreground)] truncate">
                      {s.title || "(无标题)"}
                    </span>
                    <StatusBadge status={s.status} />
                  </div>
                  <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                    <span>{s.message_count} 条消息</span>
                    <span>{s.token_count} tokens</span>
                    <span className="ml-auto">{relativeTime(s.updated_at)}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ── Right pane: Detail ── */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {!selectedId ? (
          <div className="flex-1 flex items-center justify-center text-[var(--color-muted)] text-sm">
            选择一个会话查看详情，或创建新会话
          </div>
        ) : detailLoading ? (
          <div className="flex-1 flex items-center justify-center text-[var(--color-muted)] text-sm">
            加载中...
          </div>
        ) : session ? (
          <>
            {/* Header */}
            <div className="border-b border-[var(--color-border)] p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold text-[var(--color-foreground)]">
                    {session.title || "(无标题)"}
                  </h2>
                  <StatusBadge status={session.status} />
                </div>
                <button
                  onClick={() => handleDelete(session.id)}
                  className="text-xs text-red-400 hover:text-red-300 transition"
                >
                  删除
                </button>
              </div>
              <div className="space-y-1">
                <div className="flex items-center justify-between text-xs text-[var(--color-muted)]">
                  <span>
                    Pending tokens: {session.pending_tokens} / {AUTO_COMMIT_THRESHOLD}
                  </span>
                  <span>
                    提交次数: {session.commit_count}
                  </span>
                </div>
                <div className="w-full h-1.5 bg-[var(--color-border)] rounded-full overflow-hidden">
                  <div
                    className="h-full bg-[var(--color-primary)] rounded-full transition-all"
                    style={{ width: `${tokenProgress}%` }}
                  />
                </div>
              </div>
            </div>

            {/* Tab bar */}
            <div className="flex border-b border-[var(--color-border)]">
              {([
                ["messages", "消息"],
                ["context", "上下文"],
                ["memories", "记忆"],
              ] as const).map(([key, label]) => (
                <button
                  key={key}
                  onClick={() => setActiveTab(key)}
                  className={`px-6 py-3 text-sm font-medium transition border-b-2 ${
                    activeTab === key
                      ? "border-[var(--color-primary)] text-[var(--color-foreground)]"
                      : "border-transparent text-[var(--color-muted)] hover:text-[var(--color-foreground)]"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>

            {/* Tab content */}
            <div className="flex-1 overflow-y-auto p-4">
              {activeTab === "messages" && (
                <MessagesTab
                  messages={detail?.messages ?? []}
                  messageInput={messageInput}
                  setMessageInput={setMessageInput}
                  sending={sending}
                  onSend={handleSend}
                  onCommit={handleCommit}
                  messagesEndRef={messagesEndRef}
                />
              )}
              {activeTab === "context" && (
                <ContextTab
                  ctx={ctx}
                  contextQuery={contextQuery}
                  setContextQuery={setContextQuery}
                  onSearch={handleContextSearch}
                />
              )}
              {activeTab === "memories" && (
                <MemoriesTab memories={memories} />
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-[var(--color-muted)] text-sm">
            加载会话失败
          </div>
        )}
      </div>
    </div>
  );
}

// ── Messages tab ────────────────────────────────────────────

function MessagesTab({
  messages,
  messageInput,
  setMessageInput,
  sending,
  onSend,
  onCommit,
  messagesEndRef,
}: {
  messages: SessionMessage[];
  messageInput: string;
  setMessageInput: (v: string) => void;
  sending: boolean;
  onSend: () => void;
  onCommit: () => void;
  messagesEndRef: React.RefObject<HTMLDivElement | null>;
}) {
  return (
    <div className="flex flex-col h-full">
      <div className="flex-1 overflow-y-auto space-y-3 pb-4">
        {messages.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">暂无消息</p>
        ) : (
          messages.map((msg) => (
            <div
              key={msg.id}
              className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4"
            >
              <div className="flex items-center justify-between mb-2">
                <RoleBadge role={msg.role} />
                <div className="flex items-center gap-3 text-xs text-[var(--color-muted)]">
                  <span>{msg.token_count} tokens</span>
                  <span>{msg.created_at?.slice(0, 19).replace("T", " ") ?? "—"}</span>
                </div>
              </div>
              <p className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
                {msg.content}
              </p>
            </div>
          ))
        )}
        <div ref={messagesEndRef} />
      </div>

      <div className="border-t border-[var(--color-border)] pt-4 space-y-3">
        <div className="flex gap-2">
          <textarea
            value={messageInput}
            onChange={(e) => setMessageInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                onSend();
              }
            }}
            placeholder="输入消息... (Enter 发送, Shift+Enter 换行)"
            rows={3}
            className="flex-1 border border-[var(--color-border)] rounded-lg px-3 py-2 text-sm bg-[var(--color-card)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)] resize-none"
          />
        </div>
        <div className="flex gap-2">
          <button
            onClick={onSend}
            disabled={sending || !messageInput.trim()}
            className="rounded-lg bg-[var(--color-primary)] text-white px-4 py-2 text-sm hover:opacity-90 transition disabled:opacity-50"
          >
            {sending ? "发送中..." : "发送消息"}
          </button>
          <button
            onClick={onCommit}
            className="rounded-lg border border-[var(--color-border)] text-[var(--color-foreground)] px-4 py-2 text-sm hover:bg-white/5 transition"
          >
            提交会话
          </button>
        </div>
      </div>
    </div>
  );
}

// ── Context tab ─────────────────────────────────────────────

function ContextTab({
  ctx,
  contextQuery,
  setContextQuery,
  onSearch,
}: {
  ctx: SessionContextType | null;
  contextQuery: string;
  setContextQuery: (v: string) => void;
  onSearch: () => void;
}) {
  if (!ctx) {
    return <p className="text-sm text-[var(--color-muted)]">暂无上下文数据</p>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-[var(--color-foreground)]">
          总 tokens: {ctx.total_tokens}
        </span>
        <div className="flex gap-2">
          <input
            type="text"
            placeholder="按相关性过滤..."
            value={contextQuery}
            onChange={(e) => setContextQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && onSearch()}
            className="border border-[var(--color-border)] rounded-lg px-3 py-1.5 text-sm bg-[var(--color-card)] text-[var(--color-foreground)] placeholder:text-[var(--color-muted)] focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
          />
          <button
            onClick={onSearch}
            className="rounded-lg bg-[var(--color-primary)] text-white px-3 py-1.5 text-sm hover:opacity-90 transition"
          >
            搜索
          </button>
        </div>
      </div>

      <Collapsible title={`工作记忆 (${ctx.working_memory.total_tokens} tokens)`}>
        {ctx.working_memory.sections.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">暂无工作记忆</p>
        ) : (
          <div className="space-y-2">
            {ctx.working_memory.sections.map((section, i) => (
              <pre
                key={i}
                className="text-xs text-[var(--color-foreground)] bg-black/20 rounded-lg p-3 overflow-x-auto whitespace-pre-wrap"
              >
                {typeof section === "string" ? section : JSON.stringify(section, null, 2)}
              </pre>
            ))}
          </div>
        )}
      </Collapsible>

      <Collapsible title={`长期记忆 (${ctx.long_term_memories.length})`}>
        {ctx.long_term_memories.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">暂无长期记忆</p>
        ) : (
          <div className="space-y-2">
            {ctx.long_term_memories.map((mem) => (
              <div
                key={mem.id}
                className="rounded-lg border border-[var(--color-border)] p-3"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs text-[var(--color-muted)]">
                    相关度: {(mem.relevance * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-sm text-[var(--color-foreground)]">{mem.content}</p>
              </div>
            ))}
          </div>
        )}
      </Collapsible>

      <Collapsible title={`检索结果 (${ctx.retrieval_results.length})`}>
        {ctx.retrieval_results.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">暂无检索结果</p>
        ) : (
          <div className="space-y-2">
            {ctx.retrieval_results.map((r, i) => (
              <div
                key={i}
                className="rounded-lg border border-[var(--color-border)] p-3"
              >
                <div className="flex items-center justify-between mb-1">
                  <span className="text-xs font-mono text-[var(--color-muted)]">
                    {r.substrate_id}
                  </span>
                  <span className="text-xs text-[var(--color-muted)]">
                    分数: {(r.score * 100).toFixed(0)}%
                  </span>
                </div>
                <p className="text-sm text-[var(--color-foreground)]">{r.l0_summary}</p>
              </div>
            ))}
          </div>
        )}
      </Collapsible>

      <Collapsible title="对话摘要">
        {ctx.conversation_summary ? (
          <p className="text-sm text-[var(--color-foreground)] whitespace-pre-wrap">
            {ctx.conversation_summary}
          </p>
        ) : (
          <p className="text-sm text-[var(--color-muted)]">暂无摘要</p>
        )}
      </Collapsible>
    </div>
  );
}

// ── Memories tab ────────────────────────────────────────────

function MemoriesTab({ memories }: { memories: SessionMemories | null }) {
  if (!memories || memories.memories.length === 0) {
    return (
      <div className="flex items-center justify-center h-32 text-sm text-[var(--color-muted)]">
        暂无记忆
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {memories.memories.map((mem) => (
        <div
          key={mem.id}
          className="rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] p-4"
        >
          <div className="flex items-center justify-between mb-2">
            <MemoryTypeBadge type={mem.memory_type} />
            <span className="text-xs text-[var(--color-muted)]">
              {mem.created_at?.slice(0, 19).replace("T", " ") ?? "—"}
            </span>
          </div>
          <p className="text-sm text-[var(--color-foreground)]">{mem.content}</p>
        </div>
      ))}
    </div>
  );
}
