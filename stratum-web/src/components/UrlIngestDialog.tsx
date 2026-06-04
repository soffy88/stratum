"use client";

import { useState } from "react";
import Link from "next/link";
import { apiClient } from "@/lib/api-client";

// ── Types ─────────────────────────────────────────────────────────────────────

interface FormState {
  url: string;
  title: string;
  tags: string;
  fetchMode: "full" | "summary";
  note: string;
}

interface WebClipResult {
  substrate_id: string | null;
  status: string;
  url: string;
  title: string;
  snippet: string;
  word_count: number;
  medium: string;
  tags: string[];
  message?: string;
}

type Phase = "input" | "fetching" | "success" | "error";

const INITIAL_FORM: FormState = {
  url: "",
  title: "",
  tags: "",
  fetchMode: "full",
  note: "",
};

// ── Error messages ────────────────────────────────────────────────────────────

const ERROR_HINTS: Record<string, { message: string; hint: string }> = {
  ssrf_blocked: {
    message: "URL 是内网地址，已拒绝以保护服务器安全",
    hint: "",
  },
  fetch_timeout: {
    message: "抓取超时 (>30s)，该网页可能需要登录或 JS 渲染",
    hint: "试试用浏览器扩展（扩展能用你的登录态）",
  },
  parse_failed: {
    message: "网页内容无法解析（可能是图片/视频/PDF）",
    hint: "试试直接上传文件",
  },
  too_large: {
    message: "网页内容超过 10MB 限制",
    hint: "试试复制核心段落粘贴为笔记",
  },
  not_found: {
    message: "网页 404 不存在",
    hint: "请确认 URL 正确",
  },
  auth_required: {
    message: "网页需登录访问",
    hint: "试试用浏览器扩展（扩展能用你的登录态）",
  },
  rate_limited: {
    message: "网页限制访问频率",
    hint: "稍后重试",
  },
  redirects: {
    message: "URL 发生重定向，请使用最终目标 URL",
    hint: "在浏览器打开链接，复制地址栏的真实 URL",
  },
};

function parseErrorCode(raw: string): { message: string; hint: string } {
  const entry = ERROR_HINTS[raw];
  if (entry) return entry;
  if (raw.includes("timeout") || raw.includes("504"))
    return ERROR_HINTS["fetch_timeout"]!;
  if (raw.includes("404")) return ERROR_HINTS["not_found"]!;
  if (raw.includes("redirect")) return ERROR_HINTS["redirects"]!;
  return { message: `抓取失败：${raw}`, hint: "" };
}

function hostnameOf(url: string): string {
  try {
    return new URL(url).hostname;
  } catch {
    return url;
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

export function UrlIngestDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess?: (substateId: string) => void;
}) {
  const [form, setForm] = useState<FormState>(INITIAL_FORM);
  const [phase, setPhase] = useState<Phase>("input");
  const [result, setResult] = useState<WebClipResult | null>(null);
  const [errorInfo, setErrorInfo] = useState<{ message: string; hint: string } | null>(null);

  function set(field: keyof FormState, value: string) {
    setForm((f) => ({ ...f, [field]: value }));
  }

  function resetForm() {
    setForm(INITIAL_FORM);
    setPhase("input");
    setResult(null);
    setErrorInfo(null);
  }

  async function handleFetch() {
    if (!form.url.trim()) return;
    setPhase("fetching");
    setErrorInfo(null);
    setResult(null);

    const token = apiClient.getAccessToken();
    const body = new FormData();
    body.append("url", form.url.trim());
    if (form.title.trim()) body.append("title_override", form.title.trim());
    if (form.tags.trim()) body.append("tags", form.tags.trim());
    body.append("fetch_mode", form.fetchMode);
    if (form.note.trim()) body.append("note", form.note.trim());

    try {
      const res = await fetch("/api/v1/inbox/web-clip", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body,
        credentials: "include",
      });

      if (res.status === 401) {
        setErrorInfo({ message: "未登录或会话已过期，请刷新页面", hint: "" });
        setPhase("error");
        return;
      }

      const data = await res.json();

      if (!res.ok) {
        const detail: string = data?.detail ?? String(res.status);
        setErrorInfo(parseErrorCode(detail));
        setPhase("error");
        return;
      }

      setResult(data as WebClipResult);
      setPhase("success");
      if (data.substrate_id && onSuccess) onSuccess(data.substrate_id);
    } catch (e) {
      setErrorInfo({ message: String(e), hint: "" });
      setPhase("error");
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-lg p-6 w-full max-w-lg shadow-xl max-h-[90vh] overflow-y-auto">

        {/* Header */}
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold">输入 URL 抓取网页</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-foreground)] text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* ── Input Phase ── */}
        {phase === "input" && (
          <div className="space-y-3">
            {/* URL */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                URL <span className="text-red-500">*</span>
              </label>
              <input
                type="url"
                placeholder="https://example.com/article"
                value={form.url}
                onChange={(e) => set("url", e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleFetch()}
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)]"
                autoFocus
              />
            </div>

            {/* Title */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                标题 <span className="text-[var(--color-muted)] font-normal">(可选，留空自动从网页抽取)</span>
              </label>
              <input
                type="text"
                placeholder="凯利公式 wiki"
                value={form.title}
                onChange={(e) => set("title", e.target.value)}
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)]"
              />
            </div>

            {/* Tags */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                标签 <span className="text-[var(--color-muted)] font-normal">(可选，逗号分隔)</span>
              </label>
              <input
                type="text"
                placeholder="凯利公式, quant, btc"
                value={form.tags}
                onChange={(e) => set("tags", e.target.value)}
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)]"
              />
            </div>

            {/* Fetch mode */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                内容模式
              </label>
              <div className="flex gap-4 text-sm">
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input
                    type="radio"
                    name="fetchMode"
                    value="full"
                    checked={form.fetchMode === "full"}
                    onChange={() => set("fetchMode", "full")}
                  />
                  全文
                </label>
                <label className="flex items-center gap-1.5 cursor-pointer text-[var(--color-muted)]">
                  <input
                    type="radio"
                    name="fetchMode"
                    value="summary"
                    checked={form.fetchMode === "summary"}
                    onChange={() => set("fetchMode", "summary")}
                  />
                  摘要 (LLM 提炼)
                </label>
              </div>
            </div>

            {/* Note */}
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                备注 <span className="text-[var(--color-muted)] font-normal">(可选，为什么收藏这篇)</span>
              </label>
              <textarea
                placeholder="这篇讲了凯利公式在高波动品种的实战限制..."
                value={form.note}
                onChange={(e) => set("note", e.target.value)}
                rows={2}
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)] resize-none"
              />
            </div>

            <button
              onClick={handleFetch}
              disabled={!form.url.trim()}
              className="w-full py-2 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50"
            >
              抓取并添加到知识库
            </button>
          </div>
        )}

        {/* ── Fetching Phase ── */}
        {phase === "fetching" && (
          <div className="flex flex-col items-center gap-4 py-8 text-center">
            <div className="w-8 h-8 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
            <div>
              <p className="text-sm font-medium">正在抓取 {hostnameOf(form.url)}...</p>
              <p className="text-xs text-[var(--color-muted)] mt-1">
                通常需要 5-15 秒，长文章可能更久
              </p>
            </div>
          </div>
        )}

        {/* ── Success Phase ── */}
        {phase === "success" && result && (
          <div className="space-y-4">
            <div className="p-4 bg-green-50 border border-green-200 rounded">
              <p className="text-sm font-semibold text-green-800 mb-3">✓ 抓取成功，已入库</p>
              <dl className="space-y-2 text-sm">
                <div>
                  <dt className="text-xs text-[var(--color-muted)]">标题</dt>
                  <dd className="font-medium">{result.title}</dd>
                </div>
                {result.snippet && (
                  <div>
                    <dt className="text-xs text-[var(--color-muted)]">摘要</dt>
                    <dd className="text-[var(--color-muted)] line-clamp-3 text-xs leading-relaxed">
                      {result.snippet}
                    </dd>
                  </div>
                )}
                <div className="flex gap-4">
                  <div>
                    <dt className="text-xs text-[var(--color-muted)]">字数</dt>
                    <dd>{result.word_count.toLocaleString()}</dd>
                  </div>
                  <div>
                    <dt className="text-xs text-[var(--color-muted)]">类型</dt>
                    <dd>{result.medium}</dd>
                  </div>
                  {result.tags.length > 0 && (
                    <div>
                      <dt className="text-xs text-[var(--color-muted)]">标签</dt>
                      <dd>{result.tags.join(", ")}</dd>
                    </div>
                  )}
                </div>
              </dl>
            </div>

            <div className="flex gap-2">
              {result.substrate_id && (
                <Link
                  href={`/documents/${result.substrate_id}`}
                  onClick={onClose}
                  className="px-4 py-2 bg-[var(--color-primary)] text-white rounded text-sm"
                >
                  查看完整 →
                </Link>
              )}
              <button
                onClick={resetForm}
                className="px-4 py-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)]"
              >
                继续抓另一个
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-[var(--color-muted)] hover:underline"
              >
                关闭
              </button>
            </div>
          </div>
        )}

        {/* ── Error Phase ── */}
        {phase === "error" && errorInfo && (
          <div className="space-y-4">
            <div className="p-4 bg-red-50 border border-red-200 rounded">
              <p className="text-sm font-medium text-red-800 mb-1">抓取失败</p>
              <p className="text-sm text-red-700">{errorInfo.message}</p>
              {errorInfo.hint && (
                <p className="text-xs text-red-600 mt-2">💡 {errorInfo.hint}</p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={resetForm}
                className="px-4 py-2 bg-[var(--color-primary)] text-white rounded text-sm"
              >
                重试
              </button>
              <button
                onClick={onClose}
                className="px-4 py-2 text-sm text-[var(--color-muted)] hover:underline"
              >
                关闭
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
