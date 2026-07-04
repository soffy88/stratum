"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";

const STORAGE_KEY = "stratum_onboarding_completed";

const STEPS = [
  {
    title: "欢迎使用 Stratum！",
    body: "Stratum 帮你把英文资料消化成自己的知识。只需上传文件或抓取网页，AI 会自动为你提炼要点。",
    action: null,
  },
  {
    title: "上传文件",
    body: "点击「文档」→「点击上传」可以上传 PDF、EPUB、Markdown 等格式。拖拽文件也支持。",
    action: { label: "去上传", href: "/documents" },
  },
  {
    title: "抓取网页",
    body: "点击「文档」→「输入 URL」，粘贴任意网页链接，Stratum 会自动抓取全文入库。",
    action: { label: "去抓取", href: "/documents" },
  },
  {
    title: "AI Agent",
    body: "文档入库后，点击「AI」可以运行翻译、摘要、问答 Agent，快速提炼核心内容。",
    action: { label: "去 AI 助手", href: "/ai" },
  },
  {
    title: "笔记 · 高亮 · 视图",
    body: "左侧 Sidebar 有「笔记」「高亮」「视图」等入口，可以记录批注、整理结构化知识。",
    action: null,
  },
] as const;

export function OnboardingTour() {
  const [step, setStep] = useState(0);
  const [visible, setVisible] = useState(false);
  const router = useRouter();

  useEffect(() => {
    if (typeof window !== "undefined" && !localStorage.getItem(STORAGE_KEY)) {
      setVisible(true);
    }
  }, []);

  function finish() {
    localStorage.setItem(STORAGE_KEY, "1");
    setVisible(false);
  }

  if (!visible) return null;

  const current = STEPS[step as 0 | 1 | 2 | 3 | 4];
  const isLast = step === STEPS.length - 1;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-[var(--color-background)] border border-[var(--color-border)] rounded-xl p-6 w-full max-w-md shadow-2xl">
        {/* Progress dots */}
        <div className="flex gap-1.5 mb-4">
          {STEPS.map((_, i) => (
            <div
              key={i}
              className={`h-1.5 flex-1 rounded-full transition-colors ${
                i <= step ? "bg-[var(--color-primary)]" : "bg-[var(--color-border)]"
              }`}
            />
          ))}
        </div>

        <p className="text-xs text-[var(--color-muted)] mb-1">
          {step + 1} / {STEPS.length}
        </p>
        <h2 className="text-lg font-semibold mb-2">{current.title}</h2>
        <p className="text-sm text-[var(--color-muted)] leading-relaxed mb-5">
          {current.body}
        </p>

        <div className="flex justify-between items-center">
          <button
            onClick={finish}
            className="text-xs text-[var(--color-muted)] hover:underline"
          >
            跳过引导
          </button>
          <div className="flex gap-2">
            {current.action && (
              <button
                onClick={() => {
                  router.push(current.action!.href);
                  finish();
                }}
                className="px-3 py-1.5 text-sm border border-[var(--color-border)] rounded hover:bg-[var(--color-surface)]"
              >
                {current.action.label}
              </button>
            )}
            {isLast ? (
              <button
                onClick={finish}
                className="px-4 py-1.5 text-sm bg-[var(--color-primary)] text-white rounded"
              >
                完成
              </button>
            ) : (
              <button
                onClick={() => setStep((s) => s + 1)}
                className="px-4 py-1.5 text-sm bg-[var(--color-primary)] text-white rounded"
              >
                下一步 →
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

/** Call this from /settings to let the user replay the tour */
export function resetOnboardingTour() {
  if (typeof window !== "undefined") {
    localStorage.removeItem(STORAGE_KEY);
  }
}
