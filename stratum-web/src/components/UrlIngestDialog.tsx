"use client";

import { useState } from "react";

type Result = { substrate_id: string | null; status: string; url: string; message?: string };

export function UrlIngestDialog({ onClose }: { onClose: () => void }) {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleFetch() {
    if (!url.trim()) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const body = new FormData();
      body.append("url", url.trim());
      const res = await fetch("/api/v1/inbox/web-clip", {
        method: "POST",
        body,
        credentials: "include",
      });
      if (!res.ok) {
        const text = await res.text();
        setError(`${res.status}: ${text}`);
        return;
      }
      setResult(await res.json());
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-lg p-6 w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold">输入 URL 抓取网页</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-foreground)] text-lg leading-none"
          >
            ×
          </button>
        </div>

        <input
          type="url"
          placeholder="https://example.com/article"
          value={url}
          onChange={(e) => setUrl(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && !loading && handleFetch()}
          className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm mb-3 bg-[var(--color-surface)]"
          autoFocus
        />

        <button
          onClick={handleFetch}
          disabled={loading || !url.trim()}
          className="w-full py-2 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50"
        >
          {loading ? "抓取中…" : "抓取并添加到知识库"}
        </button>

        {error && (
          <p className="mt-3 text-xs text-red-600 break-words">{error}</p>
        )}

        {result && (
          <div className="mt-3 p-3 border border-[var(--color-border)] rounded bg-[var(--color-surface)] text-xs space-y-1">
            <p>
              状态:{" "}
              <span className={result.status === "completed" ? "text-green-600" : "text-amber-600"}>
                {result.status}
              </span>
            </p>
            {result.substrate_id && (
              <p>
                已入库:{" "}
                <a
                  href={`/documents/${result.substrate_id}`}
                  className="text-[var(--color-primary)] hover:underline"
                  onClick={onClose}
                >
                  查看文档 →
                </a>
              </p>
            )}
            {result.message && <p className="text-[var(--color-muted)]">{result.message}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
