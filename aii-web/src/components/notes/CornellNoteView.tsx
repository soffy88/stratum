"use client";

/**
 * 交互式康奈尔笔记 v1.1
 * - 线索 → 模块高亮 / 自测 / 提示 / 折叠 / 掌握 ✓
 * - localStorage + CloudSyncAdapter 云端并集合并
 * - 打印样式 / 导出静态文本
 * - 默写校验(一句话记忆 / 定义 / 公式)
 */

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type {
  CornellContent,
  CornellDrill,
  CornellNote,
  CornellProgressState,
} from "@/lib/adapters/cornell";
import { CloudSyncAdapter } from "@/lib/adapters/cornell";

type ProgressState = CornellProgressState;

function storageKey(topicId: string, version = 1) {
  return `cornell_${topicId}_v${version}`;
}

function emptyProgress(topicId: string): ProgressState {
  return {
    topicId,
    version: 1,
    mastered: {},
    collapsed: {},
    drills: {},
    selfTest: false,
    showAnswers: false,
    updatedAt: new Date().toISOString(),
  };
}

function loadProgress(topicId: string): ProgressState {
  if (typeof window === "undefined") return emptyProgress(topicId);
  try {
    const raw = localStorage.getItem(storageKey(topicId));
    if (!raw) return emptyProgress(topicId);
    const p = JSON.parse(raw) as ProgressState;
    if (p.topicId !== topicId) return emptyProgress(topicId);
    return { ...emptyProgress(topicId), ...p, drills: p.drills ?? {} };
  } catch {
    return emptyProgress(topicId);
  }
}

function saveLocal(s: ProgressState) {
  s.updatedAt = new Date().toISOString();
  localStorage.setItem(storageKey(s.topicId, s.version), JSON.stringify(s));
}

function mergeProgress(a: ProgressState, b: ProgressState): ProgressState {
  const mastered = { ...a.mastered };
  for (const [k, v] of Object.entries(b.mastered || {})) {
    if (v) mastered[k] = true;
  }
  const drills = { ...(a.drills || {}), ...(b.drills || {}) };
  for (const [k, v] of Object.entries(b.drills || {})) {
    if (v) drills[k] = true;
  }
  const collapsed = { ...a.collapsed, ...b.collapsed };
  const newer = (a.updatedAt || "") >= (b.updatedAt || "") ? a : b;
  return {
    topicId: a.topicId || b.topicId,
    version: 1,
    mastered,
    collapsed,
    drills,
    selfTest: !!newer.selfTest,
    showAnswers: !!newer.showAnswers,
    updatedAt: new Date().toISOString(),
  };
}

/** 默写校验: 去空白/标点后包含度 */
function scoreAnswer(input: string, expected: string): { ok: boolean; score: number } {
  const norm = (s: string) =>
    s
      .toLowerCase()
      .replace(/[\s\u3000.,，。;；:：!！?？"'“”‘’()（）\[\]【】\-_/\\]/g, "");
  const a = norm(input);
  const b = norm(expected);
  if (!a || !b) return { ok: false, score: 0 };
  if (a === b) return { ok: true, score: 1 };
  if (b.includes(a) && a.length >= Math.min(8, b.length * 0.5)) {
    return { ok: true, score: a.length / b.length };
  }
  if (a.includes(b)) return { ok: true, score: 0.95 };
  // bigram overlap
  let hit = 0;
  for (let i = 0; i < b.length - 1; i++) {
    if (a.includes(b.slice(i, i + 2))) hit++;
  }
  const score = b.length > 1 ? hit / (b.length - 1) : 0;
  return { ok: score >= 0.55, score };
}

function SimpleMd({ text }: { text: string }) {
  const parts = text.split(/(\*\*[^*]+\*\*)/g);
  return (
    <div className="text-sm leading-relaxed whitespace-pre-wrap text-[#2C3338]">
      {parts.map((p, i) =>
        p.startsWith("**") && p.endsWith("**") ? (
          <strong key={i} className="font-semibold text-[#4A87A0]">
            {p.slice(2, -2)}
          </strong>
        ) : (
          <span key={i}>{p}</span>
        )
      )}
    </div>
  );
}

function DrillPanel({
  drills,
  progress,
  onPass,
}: {
  drills: CornellDrill[];
  progress: Record<string, boolean>;
  onPass: (id: string) => void;
}) {
  const [active, setActive] = useState(0);
  const [input, setInput] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [reveal, setReveal] = useState(false);
  if (!drills.length) return null;
  const d = drills[Math.min(active, drills.length - 1)];
  if (!d) return null;
  const passed = !!progress[d.id];

  const check = () => {
    const { ok, score } = scoreAnswer(input, d.answer);
    if (ok) {
      setFeedback(`通过（匹配度 ${(score * 100).toFixed(0)}%）`);
      onPass(d.id);
    } else {
      setFeedback(`再想想（匹配度 ${(score * 100).toFixed(0)}%）。可点「看答案」对照。`);
    }
  };

  return (
    <section className="mt-4 p-3 rounded-xl border border-[#9EC9D9] bg-white print:hidden">
      <div className="flex items-center justify-between mb-2">
        <h3 className="text-xs font-semibold text-[#4A87A0]">
          默写校验 · {active + 1}/{drills.length}
          {passed && <span className="ml-2 text-[#3D8B55]">✓ 已过</span>}
        </h3>
        <div className="flex gap-1">
          <button
            type="button"
            className="px-2 py-0.5 text-[10px] rounded border"
            disabled={active <= 0}
            onClick={() => {
              setActive((i) => i - 1);
              setInput("");
              setFeedback(null);
              setReveal(false);
            }}
          >
            上一题
          </button>
          <button
            type="button"
            className="px-2 py-0.5 text-[10px] rounded border"
            disabled={active >= drills.length - 1}
            onClick={() => {
              setActive((i) => i + 1);
              setInput("");
              setFeedback(null);
              setReveal(false);
            }}
          >
            下一题
          </button>
        </div>
      </div>
      <p className="text-sm font-medium mb-2">{d.prompt}</p>
      <textarea
        className="w-full text-sm p-2 rounded-lg border border-gray-200 min-h-[64px]"
        placeholder="闭卷默写到这里…"
        value={input}
        onChange={(e) => setInput(e.target.value)}
      />
      <div className="flex flex-wrap gap-2 mt-2">
        <button
          type="button"
          className="px-3 py-1.5 text-xs rounded-lg text-white bg-[#4A87A0]"
          onClick={check}
        >
          校验
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-xs rounded-lg border"
          onClick={() => setReveal((v) => !v)}
        >
          {reveal ? "隐藏答案" : "看答案"}
        </button>
      </div>
      {feedback && (
        <p className={`text-xs mt-2 ${passed || feedback.startsWith("通过") ? "text-[#3D8B55]" : "text-[#D17A3A]"}`}>
          {feedback}
        </p>
      )}
      {reveal && (
        <p className="text-xs mt-2 p-2 rounded bg-[#FAFAF8] border border-dashed text-[#6B7280]">
          参考：{d.answer}
        </p>
      )}
    </section>
  );
}

export function CornellNoteView({
  note,
  content: contentProp,
}: {
  note?: CornellNote;
  content?: CornellContent;
}) {
  const content = contentProp ?? note?.content;
  const topicId = content?.topicId || note?.topic_id || "unknown";
  const [state, setState] = useState<ProgressState>(() => loadProgress(topicId));
  const [activeQ, setActiveQ] = useState<string | null>(null);
  const [activeMod, setActiveMod] = useState<string | null>(null);
  const [syncOpen, setSyncOpen] = useState(false);
  const [importText, setImportText] = useState("");
  const [cloudStatus, setCloudStatus] = useState<string | null>(null);
  const pushTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  // 加载: local + 云端合并
  useEffect(() => {
    let cancelled = false;
    const local = loadProgress(topicId);
    setState(local);
    (async () => {
      const remote = await CloudSyncAdapter.pull(topicId);
      if (cancelled || !remote) return;
      const merged = mergeProgress(local, { ...emptyProgress(topicId), ...remote, topicId });
      setState(merged);
      saveLocal(merged);
      setCloudStatus("已与云端合并");
    })();
    return () => {
      cancelled = true;
    };
  }, [topicId]);

  const persist = useCallback(
    (next: ProgressState) => {
      const n = { ...next, topicId, updatedAt: new Date().toISOString() };
      setState(n);
      saveLocal(n);
      if (CloudSyncAdapter.autoPush) {
        if (pushTimer.current) clearTimeout(pushTimer.current);
        pushTimer.current = setTimeout(async () => {
          const merged = await CloudSyncAdapter.push(n, note?.id);
          if (merged) {
            setState((prev) => mergeProgress(prev, { ...merged, topicId }));
            setCloudStatus("已同步到云端");
          } else {
            setCloudStatus("云端暂不可用(仅本地)");
          }
        }, 800);
      }
    },
    [topicId, note?.id]
  );

  const cues = content?.cues ?? [];
  const modules = content?.modules ?? [];
  const drills = content?.drills ?? [];
  const totalQ = cues.length;
  const masteredN = useMemo(
    () => cues.filter((c) => state.mastered[c.id]).length,
    [cues, state.mastered]
  );
  const drillPassN = useMemo(
    () => drills.filter((d) => state.drills?.[d.id]).length,
    [drills, state.drills]
  );
  const progressPct = totalQ ? Math.round((masteredN / totalQ) * 100) : 0;

  const onCueClick = (qId: string, modId: string) => {
    setActiveQ(qId);
    setActiveMod(modId);
    if (state.collapsed[modId]) {
      persist({ ...state, collapsed: { ...state.collapsed, [modId]: false } });
    }
    requestAnimationFrame(() => {
      document.getElementById(modId)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
    });
  };

  const toggleMaster = (qId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    persist({
      ...state,
      mastered: { ...state.mastered, [qId]: !state.mastered[qId] },
    });
  };

  const toggleCollapse = (modId: string) => {
    persist({
      ...state,
      collapsed: { ...state.collapsed, [modId]: !state.collapsed[modId] },
    });
  };

  const collapseAll = (collapsed: boolean) => {
    const map: Record<string, boolean> = {};
    modules.forEach((m) => {
      map[m.id] = collapsed;
    });
    persist({ ...state, collapsed: map });
  };

  const exportJson = () => {
    const blob = new Blob([JSON.stringify(state, null, 2)], { type: "application/json" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `cornell_${topicId}_progress.json`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const exportStaticMd = () => {
    if (!content) return;
    const lines = [
      `# ${content.title}`,
      "",
      `科目: ${content.subject ?? ""} · ${content.date ?? ""}`,
      "",
      "## 线索",
      ...cues.map((q, i) => `${i + 1}. ${q.text}${state.mastered[q.id] ? " ✓" : ""}`),
      "",
      "## 笔记",
      ...modules.flatMap((m) => [`### ${m.title}`, "", m.body, ""]),
      "## 总结",
      content.summary,
      "",
      `**一句话记忆：** ${content.oneLiner}`,
      "",
    ];
    const blob = new Blob([lines.join("\n")], { type: "text/markdown;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `cornell_${topicId}.md`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  const copyJson = async () => {
    await navigator.clipboard.writeText(JSON.stringify(state, null, 2));
  };

  const doImport = () => {
    try {
      const incoming = JSON.parse(importText) as ProgressState;
      if (incoming.topicId && incoming.topicId !== topicId) {
        alert(`课题不一致: ${incoming.topicId} ≠ ${topicId}`);
        return;
      }
      persist(mergeProgress(state, { ...emptyProgress(topicId), ...incoming, topicId }));
      setSyncOpen(false);
      setImportText("");
    } catch {
      alert("JSON 解析失败");
    }
  };

  const syncNow = async () => {
    setCloudStatus("同步中…");
    const remote = await CloudSyncAdapter.pull(topicId);
    let next = state;
    if (remote) next = mergeProgress(state, { ...emptyProgress(topicId), ...remote, topicId });
    const pushed = await CloudSyncAdapter.push(next, note?.id);
    if (pushed) next = mergeProgress(next, { ...pushed, topicId });
    persist(next);
    setCloudStatus(pushed ? "云端同步完成" : "云端不可用, 已保留本地");
  };

  const resetProgress = () => {
    if (!confirm("清除本课题掌握进度？")) return;
    persist(emptyProgress(topicId));
    setActiveQ(null);
    setActiveMod(null);
  };

  if (!content) {
    return <p className="text-sm text-[var(--color-muted)]">无康奈尔内容</p>;
  }

  return (
    <div className="rounded-2xl p-4 text-[#2C3338] bg-[#FAFAF8] print:bg-white print:p-0">
      {/* 工具栏 — 打印隐藏 */}
      <div className="print:hidden flex flex-wrap gap-2 items-center mb-3">
        <button
          type="button"
          className={`px-3 py-1.5 text-xs rounded-full border border-[#4A87A0] ${
            state.selfTest ? "bg-[#9EC9D9]" : "bg-white"
          }`}
          onClick={() => persist({ ...state, selfTest: !state.selfTest })}
        >
          {state.selfTest ? "退出自测" : "自测模式"}
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-xs rounded-full border border-[#D17A3A] bg-white"
          onClick={() => persist({ ...state, showAnswers: !state.showAnswers })}
        >
          {state.showAnswers ? "隐藏提示" : "显示提示"}
        </button>
        <button type="button" className="px-3 py-1.5 text-xs rounded-full border bg-white" onClick={() => collapseAll(true)}>
          全部折叠
        </button>
        <button type="button" className="px-3 py-1.5 text-xs rounded-full border bg-white" onClick={() => collapseAll(false)}>
          全部展开
        </button>
        <button
          type="button"
          className="px-3 py-1.5 text-xs rounded-full border bg-white"
          onClick={() => {
            setActiveQ(null);
            setActiveMod(null);
          }}
        >
          清除高亮
        </button>
        <button type="button" className="px-3 py-1.5 text-xs rounded-full border bg-white" onClick={() => setSyncOpen((v) => !v)}>
          同步
        </button>
        <button type="button" className="px-3 py-1.5 text-xs rounded-full border bg-white" onClick={() => window.print()}>
          打印 / PDF
        </button>
        <button type="button" className="px-3 py-1.5 text-xs rounded-full border bg-white" onClick={exportStaticMd}>
          导出 MD
        </button>
        <button type="button" className="px-3 py-1.5 text-xs rounded-full border bg-white text-red-600" onClick={resetProgress}>
          重置进度
        </button>
        {note?.source === "machine" && (
          <span className="ml-auto text-[10px] px-2 py-1 rounded-full bg-[#A8D9B5] text-[#3D8B55]">
            机器笔记 · B仓
            {content.meta?.polished ? " · 已润色" : ""}
          </span>
        )}
        {note?.source === "human" && (
          <span className="ml-auto text-[10px] px-2 py-1 rounded-full bg-[#F5C48A] text-[#D17A3A]">人类笔记</span>
        )}
      </div>

      {/* 进度 */}
      <div className="mb-4 print:mb-2">
        <div className="flex justify-between text-xs mb-1 text-[#6B7280]">
          <span>
            掌握 {masteredN}/{totalQ}
            {drills.length > 0 && ` · 默写 ${drillPassN}/${drills.length}`}
          </span>
          <span className="print:hidden">
            {progressPct}%{cloudStatus ? ` · ${cloudStatus}` : ""}
          </span>
        </div>
        <div className="h-2 rounded-full bg-white border overflow-hidden print:hidden">
          <div className="h-full transition-all bg-gradient-to-r from-[#A8D9B5] to-[#9EC9D9]" style={{ width: `${progressPct}%` }} />
        </div>
      </div>

      {syncOpen && (
        <div className="print:hidden mb-4 p-3 rounded-xl border border-[#9EC9D9] bg-white space-y-2">
          <div className="flex gap-2 flex-wrap">
            <button type="button" className="px-2 py-1 text-xs rounded border" onClick={syncNow}>
              立即云同步
            </button>
            <button type="button" className="px-2 py-1 text-xs rounded border" onClick={exportJson}>
              导出进度 JSON
            </button>
            <button type="button" className="px-2 py-1 text-xs rounded border" onClick={copyJson}>
              复制进度
            </button>
            <button type="button" className="px-2 py-1 text-xs rounded border" onClick={exportStaticMd}>
              导出静态 MD
            </button>
          </div>
          <p className="text-[10px] text-[#6B7280]">
            CloudSyncAdapter: 登录后自动与服务器并集合并; 无网时 localStorage 仍可用。
          </p>
          <textarea
            className="w-full text-xs p-2 rounded border font-mono"
            rows={3}
            placeholder="粘贴进度 JSON 后导入…"
            value={importText}
            onChange={(e) => setImportText(e.target.value)}
          />
          <button type="button" className="px-3 py-1.5 text-xs rounded-lg text-white bg-[#4A87A0]" onClick={doImport}>
            导入并合并
          </button>
        </div>
      )}

      {/* 顶栏 */}
      <header className="mb-3 p-3 rounded-xl text-white bg-gradient-to-br from-[#4A87A0] to-[#3D8B55] print:rounded-none print:bg-[#4A87A0]">
        <div className="text-[10px] opacity-80 uppercase tracking-wider">康奈尔笔记 · Cornell</div>
        <h1 className="text-lg font-semibold mt-0.5">{content.title}</h1>
        <div className="text-xs opacity-90 mt-1 flex gap-3 flex-wrap">
          {content.subject && <span>科目 · {content.subject}</span>}
          {content.date && <span>日期 · {content.date}</span>}
          {content.meta?.ku_count != null && <span>来源 KU · {String(content.meta.ku_count)}</span>}
        </div>
      </header>

      {/* 主栏 */}
      <div
        className={`grid gap-3 ${
          state.selfTest ? "grid-cols-1" : "grid-cols-1 md:grid-cols-[minmax(180px,28%)_1fr]"
        } print:grid-cols-[28%_1fr]`}
      >
        <aside className="space-y-2">
          <div className="text-xs font-semibold px-2 py-1 rounded-lg bg-[#F5C48A] text-[#D17A3A]">线索栏 · 提问</div>
          {cues.map((q, idx) => (
            <div
              key={q.id}
              className={`p-2.5 rounded-xl border bg-white cursor-pointer transition-colors print:cursor-default ${
                activeQ === q.id ? "bg-[#9EC9D9]/40 border-[#4A87A0]" : "border-gray-200"
              } ${state.mastered[q.id] ? "border-l-[3px] border-l-[#3D8B55]" : ""}`}
              onClick={() => onCueClick(q.id, q.mod)}
            >
              <div className="flex items-start gap-2">
                <span className="text-[10px] font-mono shrink-0 mt-0.5 text-[#4A87A0]">{idx + 1}.</span>
                <div className="flex-1 min-w-0">
                  <p className="text-xs font-medium leading-snug">{q.text}</p>
                  {state.showAnswers && q.hint && (
                    <p className="text-[10px] mt-1 text-[#6B7280] print:hidden">提示：{q.hint}</p>
                  )}
                </div>
                <button
                  type="button"
                  title="标记掌握"
                  className={`print:hidden shrink-0 w-6 h-6 rounded-full border text-xs ${
                    state.mastered[q.id]
                      ? "border-[#3D8B55] bg-[#A8D9B5] text-[#3D8B55]"
                      : "border-gray-300 bg-white text-gray-400"
                  }`}
                  onClick={(e) => toggleMaster(q.id, e)}
                >
                  ✓
                </button>
              </div>
            </div>
          ))}
        </aside>

        {!state.selfTest && (
          <section className="space-y-3">
            <div className="text-xs font-semibold px-2 py-1 rounded-lg bg-[#9EC9D9] text-[#4A87A0]">笔记栏 · 记录</div>
            {modules.map((m) => {
              const isCollapsed = !!state.collapsed[m.id];
              const dimmed = activeMod != null && activeMod !== m.id;
              const highlight = activeMod === m.id;
              return (
                <article
                  key={m.id}
                  id={m.id}
                  className={`p-3 rounded-xl border bg-white transition-all print:opacity-100 print:outline-none ${
                    dimmed ? "opacity-35 grayscale-[20%] print:opacity-100 print:grayscale-0" : ""
                  } ${
                    highlight
                      ? "outline outline-2 outline-[#4A87A0] shadow-[0_0_0_4px_rgba(158,201,217,0.45)] print:shadow-none"
                      : "border-[#9EC9D9]/50"
                  }`}
                >
                  <button
                    type="button"
                    className="w-full flex items-center justify-between text-left print:pointer-events-none"
                    onClick={() => toggleCollapse(m.id)}
                  >
                    <h3 className="text-sm font-semibold text-[#4A87A0]">{m.title}</h3>
                    <span className="text-xs text-[#6B7280] print:hidden">
                      {isCollapsed ? "展开 ▾" : "折叠 ▴"}
                    </span>
                  </button>
                  <div
                    className={`mt-2 pt-2 border-t border-dashed border-gray-200 ${
                      isCollapsed ? "hidden print:block" : ""
                    }`}
                  >
                    <SimpleMd text={m.body} />
                  </div>
                </article>
              );
            })}
          </section>
        )}
      </div>

      {/* 默写 */}
      <DrillPanel
        drills={drills}
        progress={state.drills || {}}
        onPass={(id) =>
          persist({
            ...state,
            drills: { ...(state.drills || {}), [id]: true },
          })
        }
      />

      {/* 总结 */}
      <footer className="mt-4 p-3 rounded-xl border border-[#3D8B55] bg-[#A8D9B5]/25 print:bg-white">
        <div className="text-xs font-semibold mb-1 text-[#3D8B55]">总结栏 · 回顾</div>
        <p className="text-sm leading-relaxed mb-2">{content.summary}</p>
        <div className="text-sm font-medium px-3 py-2 rounded-lg bg-white border border-[#F5C48A] text-[#D17A3A]">
          一句话记忆：{content.oneLiner}
        </div>
      </footer>
    </div>
  );
}
