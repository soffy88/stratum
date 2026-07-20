"use client";

import { useCallback, useEffect, useState } from "react";
import { FolderCog, Play, Plus, Trash2, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

type Category = { folder: string; description: string; keywords: string[] };
type LogRow = {
  filename: string;
  category: string | null;
  method: string | null;
  moved_ok: boolean | null;
  ts: string | null;
};

const AII = (p: string) => `/api/aii/api${p}`;

export default function FileClassifyPage() {
  const [cats, setCats] = useState<Category[]>([]);
  const [skips, setSkips] = useState<string>("");
  const [source, setSource] = useState<string>("gdrive-rw:books/all");
  const [enabled, setEnabled] = useState<boolean>(true);
  const [log, setLog] = useState<LogRow[]>([]);
  const [busy, setBusy] = useState<string>("");
  const [msg, setMsg] = useState<string>("");

  const loadConfig = useCallback(() => {
    fetch(AII("/classify/config"))
      .then((r) => r.json())
      .then((d) => {
        const c = d?.data;
        if (!c) return;
        setCats(c.categories ?? []);
        setSkips((c.skip_patterns ?? []).join(", "));
        setSource(c.source ?? "gdrive-rw:books/all");
        setEnabled(c.enabled ?? true);
      })
      .catch(() => setMsg("读取配置失败"));
  }, []);

  const loadLog = useCallback(() => {
    fetch(AII("/classify/log?limit=30"))
      .then((r) => r.json())
      .then((d) => setLog(d?.data ?? []))
      .catch(() => {});
  }, []);

  useEffect(() => {
    loadConfig();
    loadLog();
    const t = setInterval(loadLog, 5000);
    return () => clearInterval(t);
  }, [loadConfig, loadLog]);

  const save = async () => {
    setBusy("save");
    setMsg("");
    try {
      const r = await fetch(AII("/classify/config"), {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          categories: cats.map((c) => ({
            folder: c.folder.trim(),
            description: c.description,
            keywords: (c.keywords || []).map((k) => k.trim()).filter(Boolean),
          })),
          skip_patterns: skips.split(",").map((s) => s.trim()).filter(Boolean),
          enabled,
          source: source.trim(),
        }),
      });
      const d = await r.json();
      setMsg(d?.status === "ok" ? "已保存 ✓" : "保存失败");
    } catch {
      setMsg("保存失败");
    }
    setBusy("");
  };

  const runNow = async () => {
    setBusy("run");
    setMsg("");
    try {
      await fetch(AII("/classify/run"), { method: "POST" });
      setMsg("已触发分类,结果稍后出现在下方");
    } catch {
      setMsg("触发失败");
    }
    setTimeout(loadLog, 2500);
    setBusy("");
  };

  const setCat = (i: number, patch: Partial<Category>) =>
    setCats((cs) => cs.map((c, j) => (j === i ? { ...c, ...patch } : c)));

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-3">
        <FolderCog className="w-6 h-6 text-[var(--color-primary)]" />
        <div>
          <h1 className="text-xl font-semibold text-[var(--color-foreground)]">文件分类</h1>
          <p className="text-sm text-[var(--color-muted)]">
            定期把源文件夹里的新书按下列分类自动归到对应文件夹(关键词命中优先,没命中用 AI 按描述归类)。
          </p>
        </div>
      </div>

      {/* 顶部控制 */}
      <div className="flex flex-wrap items-center gap-3 border border-[var(--color-border)] rounded-lg p-4">
        <label className="flex items-center gap-2 text-sm text-[var(--color-foreground)]">
          <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} />
          定时自动分类(每6小时)
        </label>
        <div className="flex items-center gap-2 text-sm">
          <span className="text-[var(--color-muted)]">源:</span>
          <Input value={source} onChange={(e) => setSource(e.target.value)} className="w-72" />
        </div>
        <div className="flex-1" />
        <Button onClick={runNow} disabled={busy === "run"} variant="outline" size="sm">
          <Play className="w-4 h-4 mr-1" /> 立即分类一次
        </Button>
        <Button onClick={save} disabled={busy === "save"} size="sm">
          <Save className="w-4 h-4 mr-1" /> 保存配置
        </Button>
      </div>
      {msg && <p className="text-sm text-[var(--color-primary)]">{msg}</p>}

      {/* 分类文件夹 */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-medium text-[var(--color-foreground)]">分类文件夹</h2>
          <Button
            onClick={() => setCats((cs) => [...cs, { folder: "", description: "", keywords: [] }])}
            variant="ghost"
            size="sm"
          >
            <Plus className="w-4 h-4 mr-1" /> 加一个分类
          </Button>
        </div>
        {cats.map((c, i) => (
          <div key={i} className="border border-[var(--color-border)] rounded-lg p-4 space-y-2">
            <div className="flex items-center gap-2">
              <Input
                value={c.folder}
                onChange={(e) => setCat(i, { folder: e.target.value })}
                placeholder="文件夹名(如: 数学)"
                className="w-48 font-medium"
              />
              <Input
                value={c.description}
                onChange={(e) => setCat(i, { description: e.target.value })}
                placeholder="一句话描述(AI 兜底分类用,如: 纯数学教材)"
                className="flex-1"
              />
              <Button onClick={() => setCats((cs) => cs.filter((_, j) => j !== i))} variant="ghost" size="icon">
                <Trash2 className="w-4 h-4 text-[var(--color-destructive)]" />
              </Button>
            </div>
            <textarea
              value={(c.keywords || []).join(", ")}
              onChange={(e) => setCat(i, { keywords: e.target.value.split(",").map((k) => k.replace(/\n/g, " ")) })}
              placeholder="关键词(逗号分隔,书名含任一即归此夹)"
              rows={2}
              className="w-full text-sm rounded-md border border-[var(--color-border)] bg-transparent p-2 text-[var(--color-foreground)]"
            />
          </div>
        ))}
      </div>

      {/* 跳过规则 */}
      <div className="space-y-1">
        <h2 className="text-sm font-medium text-[var(--color-foreground)]">跳过(非书,不分类)</h2>
        <textarea
          value={skips}
          onChange={(e) => setSkips(e.target.value)}
          placeholder="文件名含这些子串则跳过(逗号分隔,如: .mp4, 西游记漫画)"
          rows={2}
          className="w-full text-sm rounded-md border border-[var(--color-border)] bg-transparent p-2 text-[var(--color-foreground)]"
        />
      </div>

      {/* 最近分类结果 */}
      <div className="space-y-2">
        <h2 className="text-sm font-medium text-[var(--color-foreground)]">最近分类结果</h2>
        <div className="border border-[var(--color-border)] rounded-lg divide-y divide-[var(--color-border)]">
          {log.length === 0 && <p className="p-4 text-sm text-[var(--color-muted)]">暂无记录</p>}
          {log.map((r, i) => (
            <div key={i} className="flex items-center gap-3 p-2 text-sm">
              <span
                className={
                  r.category
                    ? "text-[var(--color-primary)] w-24 shrink-0"
                    : "text-[var(--color-muted)] w-24 shrink-0"
                }
              >
                {r.category ?? "跳过"}
              </span>
              <span className="text-[var(--color-muted)] w-12 shrink-0">{r.method}</span>
              <span className="flex-1 truncate text-[var(--color-foreground)]">{r.filename}</span>
              <span className="text-xs text-[var(--color-muted)] shrink-0">
                {r.ts ? new Date(r.ts).toLocaleString() : ""}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
