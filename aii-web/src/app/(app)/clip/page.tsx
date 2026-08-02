"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { apiClient } from "@/lib/api-client";
import { toast } from "sonner";

interface ClipResult {
  substrate_id: string | null;
  status: string;
  url: string;
  title: string;
  snippet: string;
  word_count: number;
  medium: string;
  tags: string[];
}

interface InboxItem {
  id: string;
  title: string;
  source?: string;
  created_at: string;
  meta_json?: Record<string, unknown>;
}

function bookmarkletCode(appOrigin: string): string {
  return `javascript:(function(){
  var u=encodeURIComponent(location.href);
  var t=encodeURIComponent(document.title||'');
  window.open('${appOrigin}/clip?u='+u+'&t='+t,'_blank','width=720,height=640');
})();`;
}

function ClipInner() {
  const searchParams = useSearchParams();
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const [fetchMode, setFetchMode] = useState("full");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<ClipResult | null>(null);
  const [recent, setRecent] = useState<InboxItem[]>([]);
  const [bookmarklet, setBookmarklet] = useState("");

  const loadRecent = useCallback(async () => {
    try {
      const data = await apiClient.get<{ items: InboxItem[]; count: number }>(
        "/api/v1/inbox?limit=30"
      );
      const clips = (data?.items ?? []).filter(
        (i) => (i.meta_json as Record<string, unknown>)?.medium === "webpage"
      );
      setRecent(clips.slice(0, 5));
    } catch {
      // silent
    }
  }, []);

  useEffect(() => {
    void loadRecent();
    if (typeof window !== "undefined") {
      setBookmarklet(bookmarkletCode(window.location.origin));
    }
    const u = searchParams.get("u");
    const t = searchParams.get("t");
    if (u) {
      setUrl(u);
      if (t) setTitle(t);
    }
  }, [searchParams, loadRecent]);

  const handleClip = async () => {
    const target = url.trim();
    if (!target) {
      toast.error("请输入 URL");
      return;
    }
    setBusy(true);
    try {
      const form = new FormData();
      form.append("url", target);
      form.append("fetch_mode", fetchMode);
      if (title.trim()) form.append("title_override", title.trim());
      if (tags.trim()) form.append("tags", tags.trim());

      const token = apiClient.getAccessToken?.();
      const res = await fetch("/api/v1/inbox/web-clip", {
        method: "POST",
        headers: token ? { Authorization: `Bearer ${token}` } : {},
        body: form,
        credentials: "include",
      });
      const data = await res.json();
      if (!res.ok) {
        toast.error(`剪藏失败: ${data?.detail ?? res.status}`);
        return;
      }
      setResult(data as ClipResult);
      toast.success("已保存到收件箱");
      void loadRecent();
    } catch {
      toast.error("网络错误");
    } finally {
      setBusy(false);
    }
  };

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(bookmarklet);
      toast.success("书签代码已复制");
    } catch {
      toast.error("复制失败，请手动复制");
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h1 className="text-xl font-semibold">网页剪藏</h1>
        <p className="text-sm text-[var(--color-muted)] mt-1">
          一键收藏网页到知识库，自动分类、切分、建语义索引。
        </p>
      </div>

      {/* 书签工具 */}
      <div className="p-4 border border-[var(--color-border)] rounded space-y-3">
        <p className="text-sm font-medium">浏览器书签小工具</p>
        <p className="text-xs text-[var(--color-muted)]">
          复制下面的代码，在浏览器地址栏新建书签时粘贴到地址栏；在任意网页点击书签即弹出剪藏窗口。
        </p>
        <div className="flex items-center gap-2">
          <input
            readOnly
            value={bookmarklet}
            onFocus={(e) => e.currentTarget.select()}
            className="flex-1 min-w-0 border border-[var(--color-border)] rounded px-2 py-1.5 text-xs font-mono bg-[var(--color-card)]"
          />
          <button
            onClick={() => void handleCopy()}
            className="px-3 py-1.5 text-sm rounded-lg border border-[var(--color-border)] hover:bg-[var(--color-muted)] shrink-0"
          >
            复制
          </button>
        </div>
        <p className="text-xs text-[var(--color-muted)]">
          提示: 正式域名 (aiinote.com) 生效后，请先在浏览器登录一次，剪藏窗口内可直接保存。
        </p>
      </div>

      {/* 手动剪藏 */}
      <div className="p-4 border border-[var(--color-border)] rounded space-y-3">
        <p className="text-sm font-medium">手动剪藏</p>
        <input
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          placeholder="https://example.com/article"
          className="w-full border border-[var(--color-border)] rounded px-2 py-1.5 text-sm"
        />
        <div className="grid grid-cols-2 gap-3">
          <input
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="标题覆盖 (可选)"
            className="border border-[var(--color-border)] rounded px-2 py-1.5 text-sm"
          />
          <input
            value={tags}
            onChange={(e) => setTags(e.target.value)}
            placeholder="标签, 逗号分隔 (可选)"
            className="border border-[var(--color-border)] rounded px-2 py-1.5 text-sm"
          />
        </div>
        <div className="flex items-center gap-3">
          <label className="flex items-center gap-1.5 text-sm text-[var(--color-muted)]">
            <input
              type="radio"
              name="mode"
              checked={fetchMode === "full"}
              onChange={() => setFetchMode("full")}
            />
            全文 (保留链接)
          </label>
          <label className="flex items-center gap-1.5 text-sm text-[var(--color-muted)]">
            <input
              type="radio"
              name="mode"
              checked={fetchMode === "text"}
              onChange={() => setFetchMode("text")}
            />
            纯文本
          </label>
        </div>
        <button
          onClick={() => void handleClip()}
          disabled={busy}
          className="px-4 py-2 text-sm rounded-lg bg-[var(--color-primary)] text-white disabled:opacity-50"
        >
          {busy ? "抓取中..." : "剪藏保存"}
        </button>
      </div>

      {/* 剪藏结果 */}
      {result && (
        <div className="p-4 border border-[var(--color-border)] rounded space-y-2">
          <p className="text-sm font-medium">剪藏结果</p>
          {result.substrate_id ? (
            <>
              <p className="text-sm">
                <b>{result.title}</b>
                <span className="ml-2 text-xs text-[var(--color-muted)]">
                  {result.word_count} 词 · medium={result.medium}
                </span>
              </p>
              {result.snippet && (
                <p className="text-xs text-[var(--color-muted)] line-clamp-2">
                  {result.snippet}
                </p>
              )}
              <Link
                href={`/documents/${result.substrate_id}`}
                className="text-sm text-[var(--color-primary)] hover:underline"
              >
                查看文档 →
              </Link>
            </>
          ) : (
            <p className="text-sm text-[var(--color-muted)]">
              入库失败 ({result.status})。请重试或改用全文模式。
            </p>
          )}
        </div>
      )}

      {/* 最近剪藏 */}
      <div className="space-y-2">
        <p className="text-sm font-medium">最近剪藏</p>
        {recent.length === 0 ? (
          <p className="text-sm text-[var(--color-muted)]">暂无网页剪藏记录。</p>
        ) : (
          recent.map((item) => (
            <Link
              key={item.id}
              href={`/documents/${item.id}`}
              className="block p-3 rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] hover:border-[var(--color-primary)] transition-colors"
            >
              <p className="text-sm font-medium truncate">🌐 {item.title || "未命名"}</p>
              <div className="flex items-center gap-3 mt-1">
                {item.source && (
                  <span className="text-xs text-[var(--color-muted)] truncate flex-1">
                    {item.source}
                  </span>
                )}
                <span className="text-xs text-[var(--color-muted)] shrink-0">
                  {new Date(item.created_at).toLocaleString("zh-CN")}
                </span>
              </div>
            </Link>
          ))
        )}
      </div>
    </div>
  );
}

export default function ClipPage() {
  return (
    <Suspense>
      <ClipInner />
    </Suspense>
  );
}
