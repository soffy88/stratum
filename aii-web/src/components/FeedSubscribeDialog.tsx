"use client";

import { useState } from "react";
import { apiClient } from "@/lib/api-client";

interface DiscoveredFeed {
  url: string;
  title?: string;
  type?: string;
}

type Phase = "input" | "discovering" | "select" | "subscribing" | "done" | "error";

const FREQUENCY_OPTIONS = [
  { value: 1, label: "每小时" },
  { value: 6, label: "每 6 小时" },
  { value: 24, label: "每天" },
];

export function FeedSubscribeDialog({
  onClose,
  onSuccess,
}: {
  onClose: () => void;
  onSuccess?: () => void;
}) {
  const [url, setUrl] = useState("");
  const [phase, setPhase] = useState<Phase>("input");
  const [discovered, setDiscovered] = useState<DiscoveredFeed[]>([]);
  const [selectedFeedUrl, setSelectedFeedUrl] = useState("");
  const [frequency, setFrequency] = useState(6);
  const [errorMsg, setErrorMsg] = useState("");

  async function handleDiscover() {
    if (!url.trim()) return;
    setPhase("discovering");
    setErrorMsg("");
    try {
      const data = await apiClient.get<{ feeds: DiscoveredFeed[] }>(
        `/api/v1/feeds/discover?url=${encodeURIComponent(url.trim())}`,
      );
      const feeds = data.feeds ?? [];
      if (feeds.length === 0) {
        // Try subscribing directly — the URL might already be a feed URL
        setDiscovered([{ url: url.trim(), title: "直接订阅此 URL" }]);
      } else {
        setDiscovered(feeds);
      }
      setSelectedFeedUrl(feeds[0]?.url ?? url.trim());
      setPhase("select");
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setPhase("error");
    }
  }

  async function handleSubscribe() {
    if (!selectedFeedUrl) return;
    setPhase("subscribing");
    setErrorMsg("");
    try {
      await apiClient.post("/api/v1/feeds", {
        url: selectedFeedUrl,
        frequency_hours: frequency,
      });
      setPhase("done");
      onSuccess?.();
    } catch (e) {
      setErrorMsg(e instanceof Error ? e.message : String(e));
      setPhase("error");
    }
  }

  return (
    <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-lg p-6 w-full max-w-md shadow-xl">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-base font-semibold">订阅 RSS 源</h2>
          <button
            onClick={onClose}
            className="text-[var(--color-muted)] hover:text-[var(--color-foreground)] text-xl leading-none"
          >
            ×
          </button>
        </div>

        {/* ── Input ── */}
        {phase === "input" && (
          <div className="space-y-3">
            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                网站首页或 RSS Feed URL
              </label>
              <input
                type="url"
                placeholder="https://example.com 或 https://example.com/feed.xml"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleDiscover()}
                autoFocus
                className="w-full border border-[var(--color-border)] rounded px-3 py-2 text-sm bg-[var(--color-surface)]"
              />
            </div>
            <button
              onClick={handleDiscover}
              disabled={!url.trim()}
              className="w-full py-2 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50"
            >
              检测订阅源
            </button>
          </div>
        )}

        {/* ── Discovering ── */}
        {phase === "discovering" && (
          <div className="flex items-center gap-3 py-6 justify-center">
            <div className="w-5 h-5 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-[var(--color-muted)]">正在检测订阅源...</p>
          </div>
        )}

        {/* ── Select ── */}
        {phase === "select" && (
          <div className="space-y-3">
            <p className="text-xs text-[var(--color-muted)]">
              检测到以下订阅源，选择一个订阅：
            </p>
            <ul className="space-y-1.5 max-h-48 overflow-y-auto">
              {discovered.map((f) => (
                <li key={f.url}>
                  <label className="flex items-start gap-2 p-2 border rounded cursor-pointer hover:bg-[var(--color-surface)]">
                    <input
                      type="radio"
                      name="feed"
                      value={f.url}
                      checked={selectedFeedUrl === f.url}
                      onChange={() => setSelectedFeedUrl(f.url)}
                      className="mt-0.5"
                    />
                    <span>
                      <span className="text-sm font-medium block">
                        {f.title || f.url}
                      </span>
                      <span className="text-xs text-[var(--color-muted)] break-all">
                        {f.url}
                      </span>
                    </span>
                  </label>
                </li>
              ))}
            </ul>

            <div>
              <label className="text-xs font-medium text-[var(--color-muted)] block mb-1">
                更新频率
              </label>
              <div className="flex gap-2">
                {FREQUENCY_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setFrequency(opt.value)}
                    className={`flex-1 py-1.5 text-xs rounded border transition ${
                      frequency === opt.value
                        ? "border-[var(--color-primary)] bg-[var(--color-primary)]/5 text-[var(--color-primary)]"
                        : "border-[var(--color-border)] hover:bg-[var(--color-surface)]"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="flex gap-2">
              <button
                onClick={() => setPhase("input")}
                className="flex-1 py-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)]"
              >
                返回
              </button>
              <button
                onClick={handleSubscribe}
                disabled={!selectedFeedUrl}
                className="flex-1 py-2 bg-[var(--color-primary)] text-white rounded text-sm disabled:opacity-50"
              >
                订阅
              </button>
            </div>
          </div>
        )}

        {/* ── Subscribing ── */}
        {phase === "subscribing" && (
          <div className="flex items-center gap-3 py-6 justify-center">
            <div className="w-5 h-5 border-2 border-[var(--color-primary)] border-t-transparent rounded-full animate-spin" />
            <p className="text-sm text-[var(--color-muted)]">正在订阅...</p>
          </div>
        )}

        {/* ── Done ── */}
        {phase === "done" && (
          <div className="space-y-3">
            <div className="p-4 bg-green-50 border border-green-200 rounded">
              <p className="text-sm font-semibold text-green-800">✓ 订阅成功</p>
              <p className="text-xs text-green-700 mt-1">
                新内容将自动抓取入库（每 {frequency} 小时检查一次）
              </p>
            </div>
            <button
              onClick={onClose}
              className="w-full py-2 border border-[var(--color-border)] rounded text-sm hover:bg-[var(--color-surface)]"
            >
              关闭
            </button>
          </div>
        )}

        {/* ── Error ── */}
        {phase === "error" && (
          <div className="space-y-3">
            <div className="p-4 bg-red-50 border border-red-200 rounded">
              <p className="text-sm font-medium text-red-800">操作失败</p>
              <p className="text-xs text-red-700 mt-1">{errorMsg}</p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setPhase("input")}
                className="flex-1 py-2 bg-[var(--color-primary)] text-white rounded text-sm"
              >
                重试
              </button>
              <button
                onClick={onClose}
                className="flex-1 py-2 border border-[var(--color-border)] rounded text-sm"
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
