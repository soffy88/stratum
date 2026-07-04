"use client";

// 三飞轮(econ_zh合并版经济学/math_prog数学B范式/misc其它学科)状态 + 控制。数据来自 AII 后端 /api/pipelines。
import { useEffect, useState, useCallback } from "react";

interface Book { title: string; substrate: string; ku: number; in_db: boolean; done: boolean; }
interface Channel {
  id: string; name: string; folder: string;
  ku_count: number; books_total: number; books_done: number; books: Book[];
  running: boolean; has_key: boolean; last_log: string;
}

export default function PipelinesPage() {
  const [chs, setChs] = useState<Channel[]>([]);
  const [busy, setBusy] = useState("");
  const [err, setErr] = useState(false);

  const load = useCallback(() => {
    fetch("/api/aii/api/pipelines")
      .then((r) => r.json())
      .then((d) => { setChs(d?.data ?? []); setErr(false); })
      .catch(() => setErr(true));
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

  return (
    <div className="p-6 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-1">管线通道</h1>
      <p className="text-sm text-[var(--color-muted)] mb-4">
        三飞轮状态与控制（经济学合并版 / 数学B范式(0 LLM) / 其它学科，可同时运行）。每 5 秒刷新。
      </p>
      {err && <p className="text-sm text-red-600 mb-3">无法连接 AII 后端 /api/pipelines</p>}
      <div className="space-y-3">
        {chs.map((c) => (
          <div key={c.id} className="border border-[var(--color-border)] rounded-lg p-4">
            <div className="flex items-center justify-between gap-3 flex-wrap">
              <div className="flex items-center gap-2 min-w-0">
                <span className={`w-2.5 h-2.5 rounded-full shrink-0 ${c.running ? "bg-green-500" : "bg-gray-400"}`} />
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
              <span className={c.running ? "text-green-600" : ""}>{c.running ? "● 飞轮运行中" : "○ 已停止"}</span>
              <span>书：<strong className="text-[var(--color-foreground)]">{c.books_done}/{c.books_total}</strong> 已完成</span>
              <span>KU：<strong className="text-[var(--color-foreground)]">{c.ku_count}</strong></span>
              {!c.has_key && <span className="text-amber-600 text-xs">⚠ 未配置 NIM key</span>}
            </div>
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
