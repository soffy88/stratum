"use client";

// 三飞轮(econ_zh合并版经济学/math_prog数学B范式/misc其它学科)状态 + 控制。数据来自 AII 后端 /api/pipelines。
import { useEffect, useState, useCallback } from "react";

interface Book { title: string; substrate: string; ku: number; in_db: boolean; done: boolean; }
interface CurrentBook {
  book: string; step: number | null; total_steps: number | null;
  chapters_done: number | null; chapters_total: number | null; percent: number | null;
}
interface Channel {
  id: string; name: string; folder: string;
  ku_count: number; books_total: number; books_done: number; books: Book[];
  running: boolean; has_key: boolean; last_log: string; current: CurrentBook | null;
}
interface OcrStatus {
  active: boolean; running: boolean; book?: string; total_pages?: number; pages_done?: number; percent?: number; last_book?: string;
}
interface HealthCheck { name: string; status: string; severity: "info" | "warn" | "crit"; detail: string; }
interface Health {
  overall: "ok" | "degraded" | "critical" | "unknown";
  checks: HealthCheck[]; needs_human: string[]; report_age_sec?: number;
}

export default function PipelinesPage() {
  const [chs, setChs] = useState<Channel[]>([]);
  const [ocr, setOcr] = useState<OcrStatus | null>(null);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);

  const load = useCallback(() => {
    fetch("/api/aii/api/pipelines")
      .then((r) => r.json())
      .then((d) => { setChs(d?.data ?? []); setErr(false); })
      .catch(() => setErr(true));
    fetch("/api/aii/api/ocr/status")
      .then((r) => r.json())
      .then((d) => setOcr(d?.data ?? null))
      .catch(() => {});
    fetch("/api/aii/api/health/watchdog")
      .then((r) => r.json())
      .then((d) => setHealth(d?.data ?? null))
      .catch(() => {});
  }, []);

  useEffect(() => {
    load();
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
  }, [load]);

  const ctrl = async (id: string, action: "start" | "stop") => {
    setBusy(id + action);
    try { await fetch(`/api/aii/api/pipelines/${id}/${action}`, { method: "POST" }); } catch {}
    setTimeout(() => { load(); setBusy(""); }, 1200);
  };

  const ocrCtrl = async (action: "start" | "stop") => {
    setBusy("ocr" + action);
    try { await fetch(`/api/aii/api/ocr/${action}`, { method: "POST" }); } catch {}
    setTimeout(() => { load(); setBusy(""); }, 1200);
  };

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">管线通道</h1>
      <p className="text-sm text-[var(--color-muted)] mb-4">
        三飞轮状态与控制（经济学合并版 / 数学B范式(0 LLM) / 其它学科，可同时运行）。每 5 秒刷新。
      </p>
      {health && health.overall !== "ok" && health.overall !== "unknown" && (() => {
        const crit = health.overall === "critical";
        const items = (health.needs_human?.length
          ? health.needs_human
          : health.checks.filter((c) => c.severity !== "info").map((c) => `${c.name}: ${c.detail}`));
        const stale = (health.report_age_sec ?? 0) > 900;
        return (
          <div className={`rounded-lg p-4 mb-3 border ${crit ? "border-red-500/60 bg-red-500/10" : "border-amber-500/50 bg-amber-500/10"}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className={`w-2.5 h-2.5 rounded-full ${crit ? "bg-red-500" : "bg-amber-500"}`} />
              <span className="text-sm font-semibold">
                系统健康：{crit ? "严重" : "降级"}{stale ? "（健康报告已过期，看门狗可能未运行）" : ""}
              </span>
            </div>
            <ul className="text-xs text-[var(--color-muted)] list-disc pl-5 space-y-0.5">
              {items.slice(0, 6).map((x, i) => <li key={i}>{x}</li>)}
            </ul>
          </div>
        );
      })()}
      {err && <p className="text-sm text-red-600 mb-3">无法连接 AII 后端 /api/pipelines</p>}
      {ocr && (
        <div className="border border-[var(--color-border)] rounded-lg p-4 mb-3">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2 min-w-0">
              <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${ocr.active ? "bg-green-500" : ocr.running ? "bg-amber-500" : "bg-gray-400"}`} />
              <span className="font-medium truncate">OCR 转换（ocr-vllm）</span>
            </div>
            <div className="flex gap-2 shrink-0">
              <button
                disabled={ocr.running || !!busy}
                onClick={() => ocrCtrl("start")}
                className="px-3 py-1 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
              >{busy === "ocrstart" ? "…" : "启动"}</button>
              <button
                disabled={!ocr.running || !!busy}
                onClick={() => ocrCtrl("stop")}
                className="px-3 py-1 text-sm rounded border border-[var(--color-border)] disabled:opacity-40"
              >{busy === "ocrstop" ? "…" : "停止"}</button>
            </div>
          </div>
          {ocr.active ? (
            <>
              <div className="mt-2 text-sm text-[var(--color-muted)] truncate" title={ocr.book}>
                正在转换：<strong className="text-[var(--color-foreground)]">{ocr.book}</strong>
              </div>
              <div className="mt-2 flex items-center gap-2">
                <div className="flex-1 h-2 rounded bg-[var(--color-border)] overflow-hidden">
                  <div
                    className="h-full bg-[var(--color-primary)]"
                    style={{ width: `${Math.min(100, ocr.percent ?? 0)}%` }}
                  />
                </div>
                <span className="text-xs text-[var(--color-muted)] shrink-0">
                  {ocr.pages_done}/{ocr.total_pages} 页（{ocr.percent}%）
                </span>
              </div>
            </>
          ) : (
            <div className="mt-2 text-sm text-[var(--color-muted)]">
              {ocr.running ? "◐ 空转（等待下一轮）" : "○ 已停止"}{ocr.last_book ? `（上一本：${ocr.last_book}）` : ""}
            </div>
          )}
        </div>
      )}
      <div className="space-y-3">
        {chs.map((c) => (
          <div key={c.id} className="border border-[var(--color-border)] rounded-lg p-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${c.running ? (c.current ? "bg-green-500" : "bg-amber-500") : "bg-gray-400"}`} />
                <span className="font-medium truncate">{c.name}</span>
              </div>
              <div className="flex gap-2 shrink-0">
                <button
                  disabled={c.running || !c.has_key || !!busy}
                  onClick={() => ctrl(c.id, "start")}
                  className="px-3 py-1 text-sm rounded bg-[var(--color-primary)] text-white disabled:opacity-40"
                >{busy === c.id + "start" ? "…" : "启动"}</button>
                <button
                  disabled={!c.running || !!busy}
                  onClick={() => ctrl(c.id, "stop")}
                  className="px-3 py-1 text-sm rounded border border-[var(--color-border)] disabled:opacity-40"
                >{busy === c.id + "stop" ? "…" : "停止"}</button>
              </div>
            </div>
            <div className="mt-2 text-sm text-[var(--color-muted)] flex gap-4 flex-wrap items-center">
              <span className={c.running ? (c.current ? "text-green-600" : "text-amber-600") : ""}>
                {c.running ? (c.current ? "● 运行中" : "◐ 空转（无新书可处理）") : "○ 已停止"}
              </span>
              <span>书：<strong className="text-[var(--color-foreground)]">{c.books_done}/{c.books_total}</strong> 已完成</span>
              <span>KU：<strong className="text-[var(--color-foreground)]">{c.ku_count}</strong></span>
              {!c.has_key && <span className="text-amber-600 text-xs">⚠ 未配置 NIM key</span>}
            </div>
            {c.current && (
              <div className="mt-2">
                <div className="text-sm text-[var(--color-muted)] truncate" title={c.current.book}>
                  正在抽取：<strong className="text-[var(--color-foreground)]">{c.current.book}</strong>
                  {c.current.step && c.current.total_steps && (
                    <span className="text-xs ml-1">（步骤 {c.current.step}/{c.current.total_steps}）</span>
                  )}
                </div>
                {c.current.percent != null && (
                  <div className="mt-1 flex items-center gap-2">
                    <div className="flex-1 h-2 rounded bg-[var(--color-border)] overflow-hidden">
                      <div
                        className="h-full bg-[var(--color-primary)]"
                        style={{ width: `${Math.min(100, c.current.percent)}%` }}
                      />
                    </div>
                    <span className="text-xs text-[var(--color-muted)] shrink-0">
                      {c.current.chapters_total
                        ? `第 ${c.current.chapters_done}/${c.current.chapters_total} 章（${Math.min(100, c.current.percent)}%）`
                        : `${Math.min(100, c.current.percent)}%`}
                    </span>
                  </div>
                )}
              </div>
            )}
            {c.books?.length > 0 && (
              <div className="mt-2 flex flex-col gap-1">
                {c.books.map((b) => (
                  <div key={b.substrate} className="text-xs flex items-center gap-2">
                    <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${b.done ? "bg-green-500" : b.ku ? "bg-amber-500" : "bg-gray-300"}`} />
                    <span className="truncate flex-1" title={b.title}>{b.title}</span>
                    <span className="text-[var(--color-muted)] shrink-0">{b.ku} KU{b.in_db ? "" : b.ku ? "·暂存" : ""}</span>
                  </div>
                ))}
              </div>
            )}
            {c.last_log && (
              <div className="mt-1.5 text-xs text-[var(--color-muted)] font-mono truncate" title={c.last_log}>
                {c.last_log}
              </div>
            )}
          </div>
        ))}
        {!chs.length && !err && <p className="text-[var(--color-muted)]">加载中…</p>}
      </div>
    </div>
  );
}
