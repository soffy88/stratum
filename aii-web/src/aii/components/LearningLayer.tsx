/**
 * LearningLayer — BU 学习层渲染(0011 迁移): 能力路径 + 深卡(展开/已掌握/笔记/连接)。
 * 供 /book(七项下方) 与 /books(BU 抽屉内) 共用, 单一渲染真相源。
 */
'use client';

import { useEffect, useState } from 'react';
import { MathText } from '@/aii/components/MathText';
import type { BuData, DeepCard, LearningPath } from '@/aii/types/api';

const EVIDENCE_LABEL: Record<string, string> = {
  primary: '一手来源',
  corroborated: '多源印证',
  external: '外部观察',
  inference: '框架推断',
  current: '当前事实',
};

export function LearningLayer({ substrate, paths, cards, quality, compact }: {
  substrate: string;
  paths?: LearningPath[];
  cards?: DeepCard[];
  quality?: BuData['bu_quality'];
  /** 抽屉内使用: 去掉外层卡片边框, 更紧凑 */
  compact?: boolean;
}) {
  const [open, setOpen] = useState<number | null>(null);
  const [done, setDone] = useState<Record<string, boolean>>({});
  const [notes, setNotes] = useState<Record<string, string>>({});
  const storageKey = `aii-bu-learning-${substrate}`;
  useEffect(() => {
    try {
      const raw = JSON.parse(localStorage.getItem(storageKey) || '{}');
      setDone(raw.done || {});
      setNotes(raw.notes || {});
    } catch { /* noop */ }
  }, [storageKey]);
  const persist = (d: Record<string, boolean>, n: Record<string, string>) => {
    setDone(d); setNotes(n);
    try { localStorage.setItem(storageKey, JSON.stringify({ done: d, notes: n })); } catch { /* noop */ }
  };
  if (!paths || !cards || paths.length === 0) return null;
  const byId = new Map(cards.map(c => [c.id, c]));
  const total = cards.length;
  const doneCount = cards.filter(c => done[String(c.id)]).length;
  return (
    <section className="flex flex-col gap-3">
      <div className="flex items-center gap-2">
        <h2 className="text-base font-semibold">学习层 · Learning Layer</h2>
        <span className="text-[10px] px-2 py-0.5 rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)]">
          {paths.length} 条路径 · {total} 张深卡
          {quality?.status === 'ok' ? ' · 质量门通过' : ''}
        </span>
        <span className="ml-auto text-xs text-[color:var(--text-secondary)]">{doneCount}/{total} 已掌握</span>
      </div>
      {paths.map(p => {
        const pCards = p.card_ids.map(id => byId.get(id)).filter((c): c is DeepCard => !!c);
        const pDone = pCards.filter(c => done[String(c.id)]).length;
        if (pCards.length === 0) return null;
        return (
          <div key={p.id} className={`overflow-hidden ${compact ? '' : 'rounded-lg border border-[color:var(--border)] bg-[color:var(--card)]'}`}>
            <div className="px-4 py-3 border-b border-[color:var(--border)] flex flex-col gap-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-xs text-[color:var(--accent,#2563eb)]">{p.no}</span>
                <h3 className="text-sm font-semibold">{p.name}</h3>
                <span className="ml-auto text-[10px] text-[color:var(--text-secondary)]">{pDone}/{pCards.length}</span>
              </div>
              <p className="text-xs text-[color:var(--text-secondary)]">{p.promise}</p>
            </div>
            <div className="divide-y divide-[color:var(--border)]">
              {pCards.map(c => {
                const isOpen = open === c.id;
                const isDone = !!done[String(c.id)];
                return (
                  <div key={c.id} className="px-4 py-3">
                    <button
                      onClick={() => setOpen(isOpen ? null : c.id)}
                      className="w-full text-left flex items-start gap-2 group"
                    >
                      <span className="font-mono text-[10px] text-[color:var(--text-secondary)] pt-0.5">{String(c.id).padStart(2, '0')}</span>
                      <span className="flex-1 min-w-0">
                        <span className={`text-sm font-medium ${isDone ? 'line-through opacity-60' : ''}`}>{c.name}</span>
                        <span className="block text-xs text-[color:var(--text-secondary)] leading-relaxed mt-0.5">{c.desc}</span>
                      </span>
                      <span className="flex items-center gap-1.5 shrink-0">
                        <span className="text-[10px] px-1.5 py-0.5 rounded-full border border-[color:var(--border)] text-[color:var(--text-secondary)]">
                          {EVIDENCE_LABEL[c.evidence] || c.evidence}
                        </span>
                        <span className="text-[color:var(--text-secondary)] text-xs">{isOpen ? '▴' : '▾'}</span>
                      </span>
                    </button>
                    {isOpen && (
                      <div className="mt-3 pl-5 flex flex-col gap-3 text-sm leading-relaxed">
                        <div>
                          <div className="text-[10px] font-semibold tracking-wider text-[color:var(--text-secondary)] uppercase mb-1">语境 · 原文在回应什么</div>
                          <MathText text={c.context} className="text-[color:var(--text-secondary)]" />
                        </div>
                        {c.arguments.length > 0 && (
                          <div>
                            <div className="text-[10px] font-semibold tracking-wider text-[color:var(--text-secondary)] uppercase mb-1">论证是怎么展开的</div>
                            <ol className="list-decimal pl-5 flex flex-col gap-1">
                              {c.arguments.map((a, i) => <li key={i}><MathText text={a} /></li>)}
                            </ol>
                          </div>
                        )}
                        <div>
                          <div className="text-[10px] font-semibold tracking-wider text-[color:var(--text-secondary)] uppercase mb-1">来源精读 + 原文切片</div>
                          {c.source_digest.map((d, i) => (
                            <MathText key={i} text={d} className="text-[color:var(--text-secondary)] mb-1" />
                          ))}
                          {(c.source_excerpts || []).map((x, i) => (
                            <blockquote key={i} className="mt-1 border-l-2 border-[color:var(--accent,#2563eb)]/40 pl-2 text-xs text-[color:var(--text-secondary)]">
                              <MathText text={x.text} className="line-clamp-4" />
                              <cite className="block not-italic font-mono text-[10px] opacity-70 mt-1">{x.locator}</cite>
                            </blockquote>
                          ))}
                          {c.grounding_grades && c.grounding_grades.length > 0 && (
                            <div className="mt-1 text-[10px] text-[color:var(--text-secondary)] opacity-80">
                              KU grade: {c.grounding_grades.join(' / ')}
                            </div>
                          )}
                        </div>
                        {c.boundary && (
                          <div className="rounded-md border border-amber-300/40 bg-amber-50/40 dark:bg-amber-900/10 p-3">
                            <div className="text-[10px] font-semibold tracking-wider text-amber-700 dark:text-amber-400 uppercase mb-1">别这样误用</div>
                            <MathText text={c.boundary} className="text-[color:var(--text-secondary)]" />
                          </div>
                        )}
                        <div>
                          <div className="text-[10px] font-semibold tracking-wider text-[color:var(--text-secondary)] uppercase mb-1">今天怎么用</div>
                          <MathText text={c.practice} className="font-medium" />
                          <textarea
                            rows={3}
                            value={notes[String(c.id)] || ''}
                            onChange={e => persist(done, { ...notes, [String(c.id)]: e.target.value })}
                            placeholder="写下你的答案或一个真实案例……（只保存在当前浏览器）"
                            className="mt-2 w-full rounded-md border border-[color:var(--border)] bg-[color:var(--card)] p-2 text-xs"
                          />
                        </div>
                        <div className="flex items-center gap-2">
                          <button
                            onClick={() => persist({ ...done, [String(c.id)]: !isDone }, notes)}
                            className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                              isDone
                                ? 'bg-[color:var(--accent,#2563eb)]/15 text-[color:var(--accent,#2563eb)] border-[color:var(--accent,#2563eb)]/40'
                                : 'border-[color:var(--border)] text-[color:var(--text-secondary)] hover:border-[color:var(--accent,#2563eb)]/50'
                            }`}
                          >
                            {isDone ? '✓ 已掌握 · 点击取消' : '标记为已掌握'}
                          </button>
                          {c.connections.length > 0 && (
                            <div className="flex items-center gap-1.5 flex-wrap text-[10px] text-[color:var(--text-secondary)]">
                              继续连接：
                              {c.connections.map(rid => {
                                const rc = byId.get(rid);
                                return rc ? (
                                  <button key={rid} onClick={() => setOpen(rid)}
                                    className="px-1.5 py-0.5 rounded border border-[color:var(--border)] hover:text-[color:var(--accent,#2563eb)]">
                                    {rc.name}
                                  </button>
                                ) : null;
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        );
      })}
    </section>
  );
}
