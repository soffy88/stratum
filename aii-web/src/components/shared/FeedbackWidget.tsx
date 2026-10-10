"use client";

import { useState } from "react";
import { useMutation } from "@tanstack/react-query";
import { apiClient } from "@/lib/api-client";

type WidgetState = "idle" | "open" | "submitting" | "done";

export function FeedbackWidget() {
  const [state, setState] = useState<WidgetState>("idle");
  const [content, setContent] = useState("");

  const submit = useMutation({
    mutationFn: () =>
      apiClient.post<{ status: string }>("/api/feedback", {
        content,
        page_url: typeof window !== "undefined" ? window.location.pathname : undefined,
      }),
    onMutate: () => setState("submitting"),
    onSuccess: () => {
      setState("done");
      setContent("");
    },
    onError: () => setState("open"),
  });

  if (state === "idle") {
    return (
      <button
        onClick={() => setState("open")}
        aria-label="发送反馈"
        className="fixed bottom-6 right-6 z-50 w-12 h-12 rounded-full bg-[var(--color-primary)] text-white shadow-lg flex items-center justify-center hover:opacity-90"
      >
        💬
      </button>
    );
  }

  if (state === "done") {
    return (
      <div className="fixed bottom-6 right-6 z-50 bg-white border border-[var(--color-border)] rounded-lg shadow-lg p-4 w-72 text-sm text-center">
        <p className="text-green-600 font-medium mb-2">感谢你的反馈！</p>
        <button
          onClick={() => setState("idle")}
          className="text-[var(--color-muted)] hover:underline text-xs"
        >
          关闭
        </button>
      </div>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 z-50 bg-white border border-[var(--color-border)] rounded-lg shadow-lg p-4 w-72">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">发送反馈</h3>
        <button
          onClick={() => { setState("idle"); setContent(""); }}
          className="text-[var(--color-muted)] hover:text-[var(--color-text)] text-lg leading-none"
          aria-label="关闭"
        >
          ×
        </button>
      </div>
      <textarea
        value={content}
        onChange={(e) => setContent(e.target.value)}
        placeholder="告诉我们你的想法..."
        maxLength={2000}
        rows={4}
        className="w-full text-sm border border-[var(--color-border)] rounded p-2 resize-none focus:outline-none focus:ring-1 focus:ring-[var(--color-primary)]"
      />
      <div className="flex items-center justify-between mt-2">
        <span className="text-xs text-[var(--color-muted)]">{content.length}/2000</span>
        <button
          onClick={() => submit.mutate()}
          disabled={content.trim().length === 0 || state === "submitting"}
          className="text-sm px-3 py-1.5 bg-[var(--color-primary)] text-white rounded disabled:opacity-50 hover:opacity-90"
        >
          {state === "submitting" ? "发送中..." : "发送"}
        </button>
      </div>
      {submit.isError && (
        <p className="text-xs text-red-600 mt-1">发送失败，请稍后重试</p>
      )}
    </div>
  );
}
